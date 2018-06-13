Math Genealogy
==============

Scrapers and visualizations of math genealogy.


Updating
--------

- `scrape.py` serves as a general purpose scraper of math genealogy, and returns a json array where each element corresponds to the mathematician with that id.
  If there is no data for that id, it is `null`.
- `post.jq` post processes all of the scrapped data to make it amenable to display in the web app.
- `index.js` reads the post processed data and generates an `lunr` index file.
  This proved necessary as generating the index client side took roughly twenty seconds compared to the two or three to load it.

Todo
----

- Switch to a DAG layout.

Attribution
-----------

All data comes from the [Math Genealogy Project](https://www.genealogy.math.ndsu.nodak.edu/index.php).
The favicon is courtesy of [Freepik](https://www.freepik.com/free-photos-vectors/logo)
