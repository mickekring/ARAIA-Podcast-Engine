# ARAIA-Podcast-Engine
An automated podcast creator software that fetches articles from RSS and lets GPT-4 summarize them, then sends it to MS text-to-speech. After that, it mixes all article audio toghether with intro music to a podcast episodes, updates an html page and xml-feed and uploads everything to your web server.

![araia](https://user-images.githubusercontent.com/10948066/231836806-8a325e43-9141-4733-8315-77d9251c8d06.jpg)

The image above shows the web page that's created. If you want to see this live example you can visit https://svartatavlan.mickekring.se

# Flow
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

# What you need
* A domain name and a webserver to host your podcast web page and xml feed that you submit to the podcast services of your choice
* A web server where you can use SFTP to upload files
* An OpenAI API key
* An Microsoft Azure API key

# Written in?
* Written in Python and tested with version 3.9

# How-to?
1. Download all files and folders
2. In the Music folder, change the dummy files 'intro_music.mp3' and 'divider.mp3' to your intro music and divider (short clip to highlight that there's a new article) 
3. In the 'html_web' > 'images' folder, change the dummy file 'podcast-cover-art.jpg' to your podcast cover image
4. Uplload the contents of the 'html_web' folder to the root folder of your web server, where you host your podcast
5. Open the 'config.py' file and make all changes
6. Open the 'main.py' file and make changes. My suggestion is to comment out all but the first function in the 'Main()' and make one function at a time work for you. There are still a lot of hard coded strings in the main.py file, so you'll have to do some digging. :)
7. Import all Python modules that's needed (see the imports at the top)
8. Complete the code with a 'while'-loop to make it run automatically
9. Run and (hopefully) enjoy.

# Disclaimer
I'm not a coder, so don't judge me by my code :) 
