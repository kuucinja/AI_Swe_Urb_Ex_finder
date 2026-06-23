A tool that scrapes flashback.org - a swedish forum for discussing various topics
1st step: run UrbEx_search.py – it starts crawling the domain, giving primacy to the subforum about Urban exploring
    It takes each title of the thread and sends it to gpt-os-120b hosted by BergetAI to check whether it matches urban exploration topics

2nd step: once all thread titles are crawled (which is a ginormous task in itself) the agent will take all the thread links which have been flagged to 
    correspond to Urban Exploration topics, it will go through each thread and fish out Named Entities and save them as seperate objects

3rd step: after all Named Entities have been sieved through, the agent will try and look up the named entities and match them to some geographical location:
    either specific coordinates, nearby town, etc


DISCLAIMER:
at this point only the first step works, the script scrapes the whole forum looking for anything related to urban exploration, the other agent skills
    are yet to be developed.


UPDATED PIPELINE:

1. Run UrbEx_search.py to keep discovering and classifying candidate UrbEx threads.

2. Run urbex_location_agent.py to process the UrbEx-positive threads, extract possible place/facility names from posts, geocode them, and write map outputs:

    python urbex_location_agent.py --max-threads 25 --max-items 300 --max-pages-per-thread 2

    Useful smaller test run:

    python urbex_location_agent.py --thread-url https://www.flashback.org/t279814 --max-items 25 --max-pages-per-thread 1

3. Outputs are written to data_locations:

    discovered_locations.json
    discovered_locations.geojson
    discovered_locations.csv
    discovered_locations_map.html

4. Resume state is written to data/location_agent_state.json. Delete that file if you want a clean run.

Install dependencies first if needed:

    python -m pip install -r requirements.txt
