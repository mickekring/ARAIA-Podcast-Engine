# ARAIA-Podcast-Engine
An automated podcast creator that fetches articles from RSS and lets GPT-4 summarize them, then sends it to MS text-to-speech. There after it mixes all article audio toghether with intro music to a podcast episodes, updates an html page and xml-feed and uploads everything to your web server.

# FLOW
1. Fetches all articles from the RSS feeds of your choice
2. Checks title, url and summary of artcle from RSS for keywords of your choice
3. If there's a 'hit' based on your keywords the article gets scraped
4. The scraped article is sent to GPT-4 with a prompt (of your choice) to "summarize the article in a format that can be read in one minute..." 
5. If there are enough (of your choice) articles from step 1-4 it sends all GPT created summaries to Microsofts text-to-speech. It alternates between a male and a female voice
6. A podcast intro and outro is created where the "hosts" greets you and tells you which episode you're listening to. That intro is mixed with background music, the intro music
7. The whole podcast episode gets mixed
8. The podcast xml file is created
9. The podcast website html file is created
10. All files gets uploaded to your web server


