An agent that scrapes/locates urban exploring locations in Sweden, based on flashback.org forum data:

central_script.bat - launches frontend and backend in two seperate CLI windows


Backend:
    [WRITE HERE]
Interface/Fronted:
    [WRITE HERE]
Retrieval:
    a custom built forum scraper, that collects posts from the flashback.org forum. All data is saved into ir_data.db database, which has tow
    tables:
        locations [entity, lat, lon, post_id, thread_url, confidence]
        posts [post_id, thread_url, username, time_raw, text]
    the scraper firstly gathers links to: [themes, threads, posts(text)]
        themes are Flashback subsections based on the a topic (like UrbEx)
        threads are seperate threads based on a specific question/discussion
        posts are individual user contributions and the base of the textual data the Agent uses to determine the location of UrbEx locations
        the scraper consists of these scripts which need to be adjusted and linked to the Central Agent:
            crawl_agent.py
            thread_extraction.py
            UrbEx_search.py
            and:
    UrbEx_location_agent uses different heuristics to create the location database:
        this is as preliminary as it can get and is basically just there for the sake of complete architecture
        output is geojson
    db_data/geojson_into_db.py - converts the location agents results into a look-up table to make everything faster
    data_urbex: this is where all the temp/url files are located before they get turned into the ir_data.db look-up table

Database:
    a PostgreSQL/PostGIS database that is the main only and true database for all the data collected and sorted
    repository.py:
        is the data communication layer that has all the functions the scraper (retrieval folder) and agent (backend folder) use to call up, save and manipulate data

Memory:
    session memory - the agent can remember what happens during the session
    long term memory - in the works, but long term memory should save each conversation in a seperate file
Skills:
Tools:



DISCLAIMER:
at this point only the first step works, the script scrapes the whole forum looking for anything related to urban exploration, the other agent skills
    are yet to be developed.


UPDATED PIPELINE:

All retrieval scripts import from the `database` and `backend` packages,
so they must be run as modules from the project root (not as bare
scripts, and not from inside retrieval/):

1. Run UrbEx_search.py to keep discovering and classifying candidate UrbEx
   threads. Crawl state and classification results are written straight to
   Postgres (themes/threads/thread_pages tables) - no local JSON output.

    python -m retrieval.UrbEx_search

2. Run urbex_location_agent.py to process the UrbEx-positive threads
   (read from Postgres), extract possible place/facility names from posts,
   geocode them, persist them to Postgres, and write map outputs:

    python -m retrieval.urbex_location_agent --max-threads 25 --max-items 300 --max-pages-per-thread 2

    Useful smaller test run:

    python -m retrieval.urbex_location_agent --thread-url https://www.flashback.org/t279814 --max-items 25 --max-pages-per-thread 1

3. Outputs are written to data_locations (kept for backend/orchestrator.py,
   which still reads geojson directly rather than Postgres):

    discovered_locations.json
    discovered_locations.geojson
    discovered_locations.csv

4. Resume state lives in the `location_agent_visited` table in Postgres
   (see database/schema.sql) - no local state file to delete for a clean
   run; clear that table instead.

Install dependencies first if needed:

    python -m pip install -r requirements.txt

Also requires a local PostgreSQL/PostGIS database configured via .env
(DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT) - see database/schema.sql
to create it from scratch.


PROJECT LAYOUT

interface/
    React + Vite + Tailwind frontend

retrieval/
    Flashback scraping, thread parsing, cleaning, and UrbEx location extraction

Run the frontend from:

    interface

Run the retrieval scripts from:

    retrieval
