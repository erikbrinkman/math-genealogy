Math Genealogy
==============

Scrapers and visualizations of math genealogy.


Setup
-----

To update the whole process you need `python` and `jq`.
Python can be set up with the following steps:

```
python3 -m venv . && bin/pip install -r requirements.txt
```

Python's default http server (`http.server`) is particularly slow at handling the fetch request for the large data object, for this reason node's simple http server (`http-server`) is recommended for local testing.


Updating
--------

There are three different scripts involved in the scraping process:

- `scrape.py` serves as a general purpose scraper of math genealogy, and returns a json array where each element corresponds to the mathematician with that id.
  If there is no data for that id, it is `null`.
  This downloads more data than the viewer uses, so it serves as a general purpose scraper.
- `post.jq` post processes all of the scrapped data to make it amenable to display in the web app.
  This slims down a lot of the data from the scraping process and makes it amenable to displaying on the viewer.

A full update with progress can be accomplished with the following shell script:

```
bin/python scrape.py -p | jq -f post.jq > docs/data.json
```

To Do
-----

- Switch to a DAG layout.
  Either dagre or [own implementation](http://www.it.usyd.edu.au/~shhong/fab.pdf)


Attribution
-----------

All data comes from the [Math Genealogy Project](https://www.genealogy.math.ndsu.nodak.edu/index.php).
The favicon is courtesy of [Freepik](https://www.freepik.com/free-photos-vectors/logo)
