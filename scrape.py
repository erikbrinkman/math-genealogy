import argparse
import asyncio
import contextlib
import itertools
import json
import logging
import os
import sys

from lxml import html
import aiohttp
import inflection
import tqdm
import SPARQLWrapper


_BACKUP = os.path.expanduser('~/.genealogy_backup')
_WBACKUP = os.path.expanduser('~/.genealogy_wiki_backup')


@contextlib.contextmanager
def _tqdm(total):
    fake = argparse.Namespace()
    fake.total = total
    fake.update = lambda _=1: None
    yield fake


def n(string):
    return ' '.join(string.split())


async def fetch_id(session, lock, mgpid):
    url = 'https://www.genealogy.math.ndsu.nodak.edu/id.php?id={:d}'.format(mgpid)
    async with lock, session.get(url) as response:
        text = await response.text()
    tree = html.fromstring(text)

    if tree.text == 'You have specified an ID that does not exist in the database. Please back up and try again.':
        logging.info('found no entry for id %d', mgpid)
        return {}

    logging.debug('fetched %d', mgpid)
    name = n(tree.cssselect('#mainContent h2')[0].text)
    math_scinet = tree.cssselect('#mainContent [href*="www.ams.org/mathscinet/MRAuthorID/"]')
    msn_id = int(math_scinet[0].attrib['href'].split('/')[-1]) if math_scinet else None
    descendants = [int(d.attrib['href'].split('=')[1]) for d
                   in tree.cssselect('#mainContent table tr td:first-child a')]

    titles = [e.getparent() for e in tree.cssselect('#mainContent #thesisTitle')]
    degrees = []
    if titles:
        children = titles[0].getparent().getchildren()
        for title in titles:
            start = children.index(title) - 1
            after = children[start:]
            end = next(i for i, e in enumerate(after) if e.tag == 'p')
            degree, dissert, *classif, aelem = after[:end + 1]

            span, *imgs = degree.getchildren()
            inner, = span.getchildren()
            university = n(inner.text or '')
            year = n(inner.tail)
            degree = n(span.text)
            country = [inflection.titleize(i.attrib['title'])
                       for i in imgs]

            diss = n(dissert.cssselect('#thesisTitle')[0].text)

            if classif:
                class_id, classification = classif[0].text[36:-1].split('—')
                class_id = int(class_id)
            else:
                class_id = None
                classification = ''

            alinks = aelem.cssselect('a')
            aids = (int(a.attrib['href'].split('=')[1]) for a in alinks)
            raw_tags = itertools.chain([aelem.text], (a.getnext().tail for a in alinks[:-1]))
            tags = (n(t).rstrip(':') for t in raw_tags)
            advisors = list(zip(tags, aids))

            degrees.append({
                'degree': degree,
                'university': university,
                'years': year,
                'country': country,
                'dissertation': diss,
                'subject_id': class_id,
                'subject': classification,
                'advisors': advisors,
            })

    return {
        'name': name,
        'id': mgpid,
        'msn_id': msn_id,
        'descendants': descendants,
        'degrees': degrees,
    }


async def crawl_data(session, *, progress=False, num_simult=10):
    lock = asyncio.BoundedSemaphore(num_simult)

    try:
        with open(_BACKUP) as f:
            data = json.load(f)
        existing = sum(x is not None for x in data) - 1
        logging.info('found %d existing entries out of a known %d entries',
                     existing, len(data) - 1)
    except FileNotFoundError:
        data = [{}, None]
        existing = 0

    with (tqdm.tqdm if progress else _tqdm)(total=len(data) - 1) as pbar:
        pbar.update(existing)

        async def process(datum):
            aids = itertools.chain.from_iterable(
                (aid for _, aid in d['advisors']) for d in datum['degrees'])
            new_max = 1 + max(
                itertools.chain(datum['descendants'], aids), default=0)

            futures = []
            while len(data) < new_max:
                gid = len(data)
                data.append(None)
                futures.append(fetch(gid))

            pbar.total = len(data) - 1
            pbar.update()
            await asyncio.gather(*futures)

        async def fetch(gid):
            result = data[gid] = await fetch_id(session, lock, gid)
            if result:
                await process(result)

        try:
            await asyncio.gather(*[
                fetch(gid) for gid, d in enumerate(data) if d is None])
        except:
            logging.warning('writing backup: %s', _BACKUP)
            with open(_BACKUP, 'w') as f:
                json.dump(data, f)
            raise
    return data


def fetch_mathematicians(num):
    sparql = SPARQLWrapper.SPARQLWrapper('https://query.wikidata.org/sparql')
    sparql.setQuery("""SELECT ?mathematician ?mathematicianLabel (COUNT(DISTINCT ?sitelink) AS ?sites) ?Mathematics_Genealogy_Project_ID WHERE {{
SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
?mathematician wdt:P549 ?Mathematics_Genealogy_Project_ID.
?sitelink schema:about ?mathematician.
}}
GROUP BY ?mathematician ?mathematicianLabel ?Mathematics_Genealogy_Project_ID
ORDER BY DESC(?sites)
LIMIT {:d}""".format(num))
    sparql.setReturnFormat(SPARQLWrapper.JSON)
    results = sparql.query().convert()
    return [
        {
            'wiki_id': int(result['mathematician']['value'].split('/')[-1][1:]),
            'id': int(result['Mathematics_Genealogy_Project_ID']['value']),
            'score': int(result['sites']['value'])
        } for result in results['results']['bindings']]


async def fetch_wiki_links(session, lock, ids, update):
    url = 'https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=sitelinks/urls&ids={}&sitefilter=enwiki'.format('|'.join('Q{:d}'.format(wid) for wid in ids))
    async with lock, session.get(url) as response:
        data = await response.json()
    for wid, info in data['entities'].items():
        update[int(wid[1:])] = (
            info['sitelinks']['enwiki']['url'] if 'enwiki' in info['sitelinks']
            else None)


async def fetch_wiki_links_batch(session, ids, *, num_simult=10, batch_size=50):
    lock = asyncio.BoundedSemaphore(num_simult)

    try:
        with open(_WBACKUP) as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}

    ids = list(set(ids).difference(data))
    try:
        await asyncio.gather(*[
            fetch_wiki_links(
                session, lock, ids[i * batch_size: (i + 1) * batch_size], data)
            for i in range(-(-len(ids) // batch_size))])
    except:
        logging.warning('writing wiki backup: %s', _WBACKUP)
        with open(_WBACKUP, 'w') as f:
            json.dump(data, f)
        raise
    return data


async def get_ranked_mathematicians(session, num, *, num_simult=10, batch_size=50):
    maths = fetch_mathematicians(num)
    links = await fetch_wiki_links_batch(
        session, [info['wiki_id'] for info in maths], num_simult=num_simult,
        batch_size=batch_size)
    for math in maths:
        math['wiki_link'] = links[math['wiki_id']]
    return maths


async def scrape(*, progress=False):
    async with aiohttp.ClientSession() as session:
        data, maths = await asyncio.gather(
            crawl_data(session, progress=progress),
            get_ranked_mathematicians(session, 1000))
    for math in maths:
        if len(data) > math['id']:
            data[math['id']].update(math)
        else:
            logging.warning('never fetched mgp id: %d', math['id'])
    with contextlib.suppress(FileNotFoundError):
        os.remove(_BACKUP)
    with contextlib.suppress(FileNotFoundError):
        os.remove(_WBACKUP)
    json.dump(data, sys.stdout)
    sys.stdout.write('\n')


async def parse(*ids, num_simult=10):
    lock = asyncio.BoundedSemaphore(num_simult)
    async with aiohttp.ClientSession() as session:
        futures = [fetch_id(session, lock, mgp_id) for mgp_id in ids]
        for future in futures:
            json.dump(await future, sys.stdout)
            sys.stdout.write('\n')


def main(argv):
    parser = argparse.ArgumentParser(
        description="""Scrape the math genealogy project to generate a json
        file with most of the data.""")
    parser.add_argument(
        '-v', '--verbose', action='count', default=0, help="""Increase
        verbosity of logging. By default only warnings are shown. One instance
        will also add information, two will add debugging information.""")
    parser.add_argument(
        '-p', '--progress', action='store_true', help="""Display progress bar
        for general progress.""")
    parser.add_argument(
        'ids', nargs='*', type=int, help="""If specified parse information for
        specific math genealogy project ids instead of scraping the entire site
        and adding data from popular mathematicians.""")
    args = parser.parse_args(argv)
    logging.basicConfig(
        format='%(asctime)s %(levelname)s: %(message)s',
        level=30 - 10 * min(2, args.verbose))

    loop = asyncio.get_event_loop()
    task = asyncio.ensure_future(
        parse(*args.ids) if args.ids else scrape(progress=args.progress))
    try:
        loop.run_until_complete(task)
    except KeyboardInterrupt:
        task.cancel()
        loop.run_forever()
        raise
    finally:
        with contextlib.suppress(asyncio.CancelledError, SystemExit):
            task.exception()


if __name__ == '__main__':
    main(sys.argv[1:])
