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