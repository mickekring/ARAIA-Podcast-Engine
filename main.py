

### ARAIA
### Version: 1.0.1
### Author: Micke Kring
### Contact: jag@mickekring.se


import feedparser
import requests
from bs4 import BeautifulSoup
import config as c
from openai import OpenAI
import requests
import json
import os
from tinydb import TinyDB, Query, where
import re
from time import sleep
from xml.etree import ElementTree
from pydub import AudioSegment
import datetime
import random
import paramiko
import pytz
import newspaper

import numpy as np

client = OpenAI(api_key = c.OPEN_AI_API_KEY)

db = TinyDB("db.json")
episodes_table = db.table("episodes")



class Colors:
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    RESET = '\033[0m'



### 1. Reads all RSS and feeds, looks for matching keyword then stores that information to the database

def read_rss_and_find_articles():

    print(f"--- --- --- ---\n\n{Colors.GREEN}1. LOOKING FOR ARTICLES FROM FEEDS{Colors.RESET}")

    articles = []
    Article = Query()

    def contains_keyword(text):

        return any(re.search(rf"\b{keyword.lower()}\b", text.lower()) for keyword in c.keywords)


    for url in c.rss_urls:
        feed = feedparser.parse(url)

        print("\n--- --- --- --- --- ---\n")
        print("Feed Title:", feed.feed.title)
        print("Feed Link:", feed.feed.link)
        print()


        for entry in feed.entries[:20]:
            if contains_keyword(entry.title) or contains_keyword(entry.summary) or contains_keyword(entry.link):
                existing_entry = db.search(Article.Title == entry.title)

                if not existing_entry:
                    db.insert({"Title": entry.title, "Link": entry.link, "Date": entry.published, 
                        "Summary": entry.summary, "FullText": "", "GPTText": "", "AudioFile": "", 
                        "Voice": "", "Language": "sv", "Source": feed.feed.title, "Published": False, })
                    articles.append(entry)
                    print(f"{Colors.GREEN}STORED in DB:{Colors.RESET} {entry.title}")
                else:
                    print(f"{Colors.BLUE}ALREADY STORED in DB:{Colors.RESET} {entry.title}")

            else:
                print(f"{Colors.RED}NO KEYWORDS FOUND:{Colors.RESET} {entry.title}")

# Function for web scraping. Will be obsolete when GPT accepts urls.

# CHANGE: Based on what sections, divs or classes for the different urls.

def get_article_text(url, source):

    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        article_text = ''
  

        # First, what section, div or other of the article content

        if source == "IT-Pedagogen.se":
            editorial_div = soup.find('div', class_='post-entry')
        
        elif source == "ViLärare | Nyheter":
            editorial_div = soup.find('main', class_='content')
        
        elif source == "Inrikes | SVT Nyheter":
            editorial_div = soup.find('article', class_='nyh_article')

        elif source == "Skola - Skola och Samhälle":
            editorial_div = soup.find('div', class_='article')
        
        elif source == "Skola-arkiv - Spaningen":
            editorial_div = soup.find('div', class_='entry-content')
        
        elif source == "RSS - Regeringen.se":
            editorial_div = soup.find('div', class_='col-1')
        
        elif source == "Skolledaren":
            editorial_div = soup.find('div', class_='editorial')
        
        elif source == "Utbildning & skola-arkiv - forskning.se":
            editorial_div = soup.find('section', class_='content')
        
        else:
            editorial_div = soup.find('main', class_='content')


        # Secondly, what to scrape, eg <p>, <h2>
        
        if editorial_div and source == "ViLärare | Nyheter":

            for paragraph in editorial_div.find_all('p'):
                article_text += paragraph.get_text()

        elif editorial_div and source == "IT-Pedagogen.se":

            for element in editorial_div.find_all(['p', 'h2', 'h4']):
                article_text += element.get_text()

        elif editorial_div and source == "Inrikes | SVT Nyheter":

            for paragraph in editorial_div.find_all('p'):
                article_text += paragraph.get_text()

        elif editorial_div and source == "Skola-arkiv - Spaningen":

            for element in editorial_div.find_all(['p', 'h2']):
                article_text += element.get_text()

        elif editorial_div and source == "Skola - Skola och Samhälle":

            for element in editorial_div.find_all('p'):
                article_text += element.get_text()

        elif editorial_div and source == "Skolledaren":

            for element in editorial_div.find_all(['p', 'h2']):
                article_text += element.get_text()

        elif editorial_div and source == "Utbildning & skola-arkiv - forskning.se":

            for element in editorial_div.find_all(['p', 'h2']):
                article_text += element.get_text()

        elif editorial_div and source == "RSS - Regeringen.se":

            for paragraph in editorial_div.find_all('p'):
                article_text += paragraph.get_text()

        return article_text
    else:
        return None



# 2. Scraping the full article to be sent to GPT for summary. Will be obsolete when
# GPT accepts links 

def scrape_article():

    print(f"--- --- --- ---\n\n{Colors.GREEN}2. FETCHING FULL TEXT FROM ARTICLE{Colors.RESET}\n")

    # Query the database for entries with an empty "FullText"
    entries_to_scrape = db.search(where('FullText') == '')

    # Iterate through the results
    for entry in entries_to_scrape:
        # Get the entry's URL and source
        url = entry['Link']
        source = entry['Source']

        # Scrape the article text
        article_text = get_article_text(url, source)

        if article_text:
            # Update the "FullText" field in the database
            db.update({'FullText': article_text}, where('Link') == url)
            print(f"{Colors.GREEN}UPDATED ENTRY{Colors.RESET} '{entry['Title']}' with full article text.")
        else:
            print(f"{Colors.RED}FAILED TO FETCH{Colors.RESET} the article for entry '{entry['Title']}'.")

    print(f"\n{Colors.GREEN}FULL TEXT - ALL DONE{Colors.RESET}\n")



# 3. Sending transcription to GPT based on choice of template
# Has fallback to GPT-3.5 if 4 is over limits

# CHANGE: Change the prompt primer that goes before the full article
# to GPT.

def send_to_gpt():

    print(f"--- --- --- ---\n\n{Colors.GREEN}3. PROCESSING TEXT WITH GPT{Colors.RESET}\n")

    # Query the database for entries with content in "FullText" but empty in "GPTText"
    entries_to_process = db.search((where('FullText') != '') & (where('GPTText') == ''))

    # Iterate through the results
    for entry in entries_to_process:
        # Get the entry's FullText
        full_text = entry['FullText']
        print(f"{Colors.GREEN}SENDING TEXT:{Colors.RESET} {entry['Title']} to GPT...")

        # Send FullText to GPT
        messages = []
        prompt_primer = f"Agera som journalist. Sammanfatta artikeln med titeln - {entry['Title']} - i ett format som går att \
                        läsa upp på cirka 60 sekunder. Texten är ett inslag i en podcast. Formattera texten utan att använda  \
                        SSML format för Microsofts TTS så att det låter mer naturligt.\n---\n\n"

        #print(prompt_primer)

        messages.append({"role": "user", "content": prompt_primer + "\n\n---\n" + full_text})

        try:
            completion = client.chat.completions.create(model="gpt-4", messages=messages)
            print("GPT-4")
        except:
            completion = client.chat.completions.create(model="gpt-3.5-turbo", messages=messages)
            print("GPT-3")

        chat_response = completion.choices[0].message.content

        # Update the "GPTText" field in the database with the chat_response
        db.update({'GPTText': chat_response}, where('Link') == entry['Link'])

        print(chat_response)
        print()

        print(f"{Colors.GREEN}UPDATED ENTRY{Colors.RESET} '{entry['Title']}' with GPT-generated text.")
        print()

    print(f"\n{Colors.GREEN}GPT - ALL DONE{Colors.RESET}\n")


# Function for text-to-speech using Microsoft TTS.

# CHANGE: Hardcoded text and voices

def text_to_speech():
    
    voice = "female"

    entries_to_process = db.search((where('GPTText') != '') & (where('AudioFile') == ''))

    for entry in entries_to_process:

        url = "https://bff.listnr.tech/api/tts/v1/convert-text"

        title = entry['Title']
        source = entry['Source']
        gpt_text_to_send = entry['GPTText']

        text_to_send = f"{title}. {gpt_text_to_send} Artikeln finns att läsa på {source}"

        print(text_to_send)
        print()


        if voice == "male":

            payload = json.dumps({
              "ssml": "<speak>" + text_to_send + "</speak>", "voice": "sv-SE-MattiasNeural"})

        else:

            payload = json.dumps({
              "ssml": "<speak>" + text_to_send + "</speak>", "voice": "sv-SE-SofieNeural"})


        headers = {'x-listnr-token': c.X_LISTNR_TOKEN,'Content-Type': 'application/json'}

        response = requests.request("POST", url, headers=headers, data=payload)
        response_json = response.json()

        print()
        print(response.text)

        # Extract the URL from the response
        audio_url = response_json.get('url')

        # Download the audio file
        audio_response = requests.get(audio_url)
        audio_key = response_json.get('audioKey')

        # Save the audio file to the 'audio' folder
        audio_folder = 'audio'
        os.makedirs(audio_folder, exist_ok=True)
        audio_filename = os.path.join(audio_folder, f'{audio_key}.mp3')

        with open(audio_filename, 'wb') as f:
            f.write(audio_response.content)

        print()
        print(f"Audio file saved to: {audio_filename}")

        db.update({'AudioFile': audio_filename}, where('Link') == entry['Link'])

        if voice == "male":
            voice = "female"
        else:
            voice = "male"



# 4. Sends text to TTS. 

# CHANGE: The words in the dictionary and hard coded strings

def find_text_to_convert_to_speech():

    print(f"--- --- --- ---\n\n{Colors.GREEN}4. SENDING TEXT TO TEXT-TO-SPEECH{Colors.RESET}\n")

    voice = "male"

    entries_to_process = db.search((where('GPTText') != '') & (where('AudioFile') == ''))

    
    # A dictionary of word to be replaced to make the text-to-speech work better. In swedish this
    # is mostly used for phonetic replacement of abbreviations and english words.
    words_to_replace = {'ViLärare | Nyheter': 'Vi Lärare', 'IT-Pedagogen.se': 'I T pedagogen', 
                        'Binogi': 'Binågi', 'NP': 'Nationella prov', 'chattbotar': 'chattbottar', 
                        'chatbot': 'chttbott', 'machine learning': 'maskininlärning', 
                        'eye-to-speech': 'aj-tu-spiitsch', 'iTrack Reading': 'ajTrack Riiding', 
                        'Chatboten': 'Chattbotten', 'RISE': 'Rajs', 'Rise': 'Rajs', 'heat': 'hit', 
                        'maps': 'kartor', '"': '', '&': 'och', 'Skola-arkiv - Spaningen': 'Spaningen.se',
                        'm.m.': 'med mera', 'Inrikes | SVT Nyheter': 'SVT Nyheter', 
                        'RSS - Regeringen.se': 'Regeringen.se', 'Utbildning & skola-arkiv - forskning.se': 'Forskning.se', 
                        'Skola - Skola och Samhälle':'Skola och Samhälle'}

    for entry in entries_to_process:

        title = entry['Title']
        source = entry['Source']
        gpt_text_to_send = entry['GPTText']

        if voice == "male":

            voice_person = "sv-SE-MattiasNeural"

        else:

            voice_person = "sv-SE-SofieNeural"

        text_to_send = f"<voice name='{voice_person}'><prosody rate='+12%'>{title}. {gpt_text_to_send} Artikeln finns att läsa på {source}</prosody></voice>"

        for key, value in words_to_replace.items():
            text_to_send = text_to_send.replace(key, value)

        print(text_to_send)
        print()

        text_to_speech_azure(title, text_to_send, voice_person)

        audio_filename = text_to_speech_azure(title, text_to_send, voice_person)
        print(f"{Colors.GREEN}AUDIO FILE SAVED{Colors.RESET} as {audio_filename}.")

        if audio_filename:
            db.update({'AudioFile': audio_filename, 'Voice': voice}, where('Link') == entry['Link'])

        if voice == "male":
            voice = "female"
        else:
            voice = "male"

    print(f"\n{Colors.GREEN}TEXT TO SPEECH - ALL DONE{Colors.RESET}\n")



# Function for TTS

# CHANGE: Output format, language and more

def text_to_speech_azure(title, text_to_send, voice_person):

    output_file = f"audio/{title}.mp3"

    headers = {
        "Ocp-Apim-Subscription-Key": c.AZURE_API_KEY,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-48khz-192kbitrate-mono-mp3",
        "User-Agent": "Azure-TTS"
    }

    ssml = f"""
    <speak version='1.0' xmlns='https://www.w3.org/2001/10/synthesis' xml:lang='sv-SE'>
        
            {text_to_send}
        
    </speak>
    """

    endpoint = f"https://{c.AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
    response = requests.post(endpoint, headers=headers, data=ssml.encode("utf-8"))

    if response.status_code == 200:
        with open(output_file, "wb") as audio_file:
            audio_file.write(response.content)

        return output_file
    else:
        print(f"Error: {response.status_code}. {response.reason}.")



# 6. Mixing podcast

def mix_and_create_podcast_episode():

    print(f"--- --- --- ---\n\n{Colors.GREEN}6. CREATING PODCAST EPISODE BY MIXING AUDIO FILES{Colors.RESET}\n")

    # Query the database for entries with an AudioFile and not Published
    entries_to_mix = db.search((where('AudioFile') != '') & (where('Published') == False))

    # Initialize an empty AudioSegment
    mixed_audio = AudioSegment.empty()

    # Initialize a list to store the included titles
    included_titles = []
    
    # Iterate through the entries to mix and create the podcast episode

    audio = AudioSegment.from_mp3("audio/intro.mp3")
    mixed_audio += audio

    for i, entry in enumerate(entries_to_mix):
        # Load the audio file
        audio = AudioSegment.from_mp3(entry["AudioFile"])

        # Add the title and the URL to the included_titles list
        included_titles.append({"title": entry["Title"], "url": entry["Link"]})

        # Append the audio to the mixed_audio variable
        mixed_audio += audio

        # Add some silence between audio segments
        #mixed_audio += AudioSegment.silent(duration=500)  # 1 seconds of silence

        audio = AudioSegment.from_mp3("music/divider.mp3")
        mixed_audio += audio

    audio = AudioSegment.from_mp3("audio/outro.mp3")
    mixed_audio += audio

    # Get the next episode number
    episode_number = len(episodes_table) + 1

    # Save the mixed audio to a file
    output_filename = f"audio_episodes/{episode_number}_podcast_episode.mp3"
    mixed_audio.export(output_filename, format="mp3", bitrate="192k", parameters=["-ac", "2"])

    # Calculate the file size in bytes
    file_size_bytes = os.path.getsize(output_filename)


    # Get the current date and time
    now = datetime.datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M")
    formatted_pub_date = now.strftime("%a, %d %b %Y %H:%M:%S %Z")

    # Calculate the duration of the mixed audio and format it
    mixed_audio_duration = len(mixed_audio)
    formatted_duration = format_duration(mixed_audio_duration)

    # Store the episode information in the episodes table
    episodes_table.insert({
        "Date": date,
        "Time": time,
        "Episode": episode_number,
        "AudioFile": output_filename,
        "FeedCode": "",
        "HtmlCode": "",
        "IncludedTitles": included_titles,
        "Duration": formatted_duration,
        "Length": file_size_bytes,
        "PublishDate": formatted_pub_date
    })

    # Mark the entries as Published in the database
    for entry in entries_to_mix:
        db.update({'Published': True}, where('Link') == entry['Link'])

    print(f"\n{Colors.GREEN}PODCAST EPISODE CREATED - {output_filename}{Colors.RESET}\n")



def format_duration(duration_ms):
    duration_s = duration_ms // 1000
    hours, remainder = divmod(duration_s, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"



# Creates the xml feed that you submit to eg Apple Podcasts

def create_xml_feed():

    print(f"--- --- --- ---\n\n{Colors.GREEN}7. CREATING XML FEED{Colors.RESET}\n")

    channel_intro = f'''<?xml version="1.0" encoding="UTF-8"?>
    <rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:spotify="https://www.spotify.com/ns/rss" version="2.0">
    <channel>
    <title>{c.podcast_title}</title>
    <link>{c.podcast_website}</link>
    <language>{c.language}</language>
    <copyright>{c.copyright}</copyright>
    <itunes:subtitle>{c.subtitle}</itunes:subtitle>
    <itunes:author>{c.author}</itunes:author>
    <itunes:summary>{c.summary}</itunes:summary>
    <description>{c.summary}</description>
    <itunes:owner>
      <itunes:name>{c.author}</itunes:name>
      <itunes:email>{c.owner_email}</itunes:email>
    </itunes:owner>
    <itunes:image href="{c.image_url}" />
    <itunes:category text="{c.main_category}">
      <itunes:category text="{c.subcategory}" />
    </itunes:category>
    <itunes:explicit>{c.explicit}</itunes:explicit>
    <spotify:countryOfOrigin>{c.country_of_origin}</spotify:countryOfOrigin>

    '''

    channel_outro = '''

    </channel>
    </rss>

    '''

    podcast_feed_content = [channel_intro]

    # Iterate through all episodes in the database
    #for episode_info in episodes_table:
    for episode_info in sorted(episodes_table.all(), key=lambda x: x['Episode'], reverse=True):

        episode = f'''
        <item>
          <title>Avsnitt {episode_info["Episode"]}</title>
          <itunes:author>{c.author}</itunes:author>
          <itunes:subtitle>{c.subtitle}</itunes:subtitle>
          <itunes:summary>{c.summary}</itunes:summary>
          <description>{c.summary}</description>
          <enclosure url="{c.remote_audio_directory}{episode_info["AudioFile"]}" length="{episode_info["Length"]}" type="audio/mpeg" />
          <guid>{c.remote_audio_directory}{episode_info["AudioFile"]}</guid>
          <pubDate>{episode_info["PublishDate"]}</pubDate>
          <itunes:duration>{episode_info["Duration"]}</itunes:duration>
          <itunes:explicit>{c.explicit}</itunes:explicit>
          <itunes:episode>{episode_info["Episode"]}</itunes:episode>
          <itunes:season>1</itunes:season>
        </item>
        '''

        podcast_feed_content.append(episode)

    podcast_feed_content.append(channel_outro)

    with open("feed/podcast_feed.xml", "w") as f:
        f.write("\n".join(podcast_feed_content))

    print(f"\n{Colors.GREEN}CREATING XML FEED - ALL DONE{Colors.RESET}\n")



# Creates the podcast intro and outro, by sending greetings text to TTS and combining it
# with the background music

# CHANGE: Hard coded strings

def create_pocast_intro_and_outro():

    print(f"--- --- --- ---\n\n{Colors.GREEN}5. CREATING PODCAST INTRO AND OUTRO{Colors.RESET}\n")

    episode_number = len(episodes_table) + 1

    female_voice_1 = f"<voice name='sv-SE-SofieNeural'><prosody rate='+15%'>Hej och välkomna till {c.podcast_title}! - podden som håller dig uppdaterad om skolans digitalisering. Jag är er värd, {c.name_host_female}.</prosody></voice>"
    male_voice_1 = f"<voice name='sv-SE-MattiasNeural'><prosody rate='+15%'>Och jag heter {c.name_host_male}. I avsnitt {episode_number} dyker vi direkt in i de senaste nyheterna och trenderna. Häng med och bli en del av diskussionen!</prosody></voice>"

    female_voice_2 = f"<voice name='sv-SE-SofieNeural'><prosody rate='+15%'>Hej och tack för att ni lyssnar på {c.podcast_title} – podden som ger er en dos av skolans digitala utveckling! Jag är {c.name_host_female}.</prosody></voice>"
    male_voice_2 = f"<voice name='sv-SE-MattiasNeural'><prosody rate='+15%'>Och jag är {c.name_host_male} och i avsnitt {episode_number} tar vi er med på en resa genom de mest aktuella nyheterna och trenderna. Häng med!</prosody></voice>"

    female_voice_3 = f"<voice name='sv-SE-SofieNeural'><prosody rate='+15%'>Välkomna till {c.podcast_title}, där vi ömvärldsbevakar kring skolans digitalisering! Jag är er värd, {c.name_host_female}.</prosody></voice>"
    male_voice_3 = f"<voice name='sv-SE-MattiasNeural'><prosody rate='+15%'>Och jag är {c.name_host_male}, och i avsnitt {episode_number} ger vi er en inblick i de främsta digitala nyheterna och trenderna. Låt oss dyka in!</prosody></voice>"

    outro_female = "<voice name='sv-SE-SofieNeural'><prosody rate='+15%'>Det var allt för från oss denna gång! Tack för att ni lyssnat. Hejdå!</prosody></voice>"
    outro_male = "<voice name='sv-SE-MattiasNeural'><prosody rate='+15%'>Och hejdå från mig. Som vanligt hittar ni alla länkar till artiklarna på svartatavlan punkt mickekring.se</prosody></voice>"


    random_talk = random.randint(1, 3)

    if random_talk == 1:
        intro_talk = f"{female_voice_1} {male_voice_1}"
    elif random_talk == 2:
        intro_talk = f"{female_voice_2} {male_voice_2}"
    else:
        intro_talk = f"{female_voice_3} {male_voice_3}"


    outro_talk = f"{outro_female} {outro_male}"


    print(random_talk)
    print(intro_talk)


    text_to_speech_azure("intro_voice", intro_talk, "female")

    audio_filename = text_to_speech_azure("intro_voice", intro_talk, "female")
    print(f"{Colors.GREEN}AUDIO FILE SAVED{Colors.RESET} as {audio_filename}.")


    print(outro_talk)


    text_to_speech_azure("outro_voice", outro_talk, "female")

    audio_filename = text_to_speech_azure("outro_voice", outro_talk, "female")
    print(f"{Colors.GREEN}AUDIO FILE SAVED{Colors.RESET} as {audio_filename}.")


    # Mix intro and outro with music
    voiceover_path = "audio/intro_voice.mp3"
    music_path = "music/intro_music.mp3"
    output_path = "audio/intro.mp3"
    mix_voiceover_and_music(voiceover_path, music_path, output_path)

    voiceover_path = "audio/outro_voice.mp3"
    music_path = "music/intro_music.mp3"
    output_path = "audio/outro.mp3"
    mix_voiceover_and_music(voiceover_path, music_path, output_path)

    print(f"\n{Colors.GREEN}INTRO AND OUTRO - ALL DONE{Colors.RESET}\n")



# Sets the background music in the intro to -5 in gain. After 17.3 seconds it raises the
# volume to 0 in gain.

def mix_voiceover_and_music(voiceover_path, music_path, output_path, music_gain=-5, volume_change_time=17300):
    # Load the voiceover and background music files
    voiceover = AudioSegment.from_mp3(voiceover_path)
    music = AudioSegment.from_mp3(music_path)

    # Lower the volume of the background music
    music = music + music_gain

    # Split the background music into two parts: before and after the volume change
    music_before_volume_change = music[:volume_change_time]
    music_after_volume_change = music[volume_change_time:]

    # Increase the volume of the second part to 0 dB
    music_after_volume_change = music_after_volume_change - music_gain

    # Combine the two parts back together
    music = music_before_volume_change + music_after_volume_change

    # Overlay the voiceover on the background music
    mixed_audio = music.overlay(voiceover)

    # Export the mixed audio to an output file
    mixed_audio.export(output_path, format="mp3")



# Creates the web page for the podcast

# CHANGE: Hard coded text and links

def create_html_feed():

    print(f"--- --- --- ---\n\n{Colors.GREEN}8. CREATING HTML SITE{Colors.RESET}\n")

    html_intro = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{c.podcast_title}</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <header>
        <h1>{c.podcast_title}</h1>
        <p>{c.subtitle}</p>
        <p><a href="{c.spotify_podcast_url}">Spotify</a> | <a href="{c.apple_podcast_url}">Apple Podcast</a> | <a href="{c.google_podcast_url}">Google Podcast</a> | <a href="https://svartatavlan.mickekring.se/podcast_feed.xml">RSS</a></p>
        <p class="header-meta"><strong>Redation:</strong> ARAIA Podcast Engine och GPT-4 | <strong>Värdar:</strong> Diana och Bob, MS TTS | <strong>Musik:</strong> Soundraw</p>
    </header>
    <main>
        <ul class="episode-list">
    '''

    html_outro = '''
        </ul>
    </main>
</body>
</html>
    '''

    episode_list_content = [html_intro]

    for episode_info in sorted(episodes_table.all(), key=lambda x: x['Episode'], reverse=True):
        
        included_titles_html = ''
        
        for title_info in episode_info["IncludedTitles"]:
            included_titles_html += f'<li><a href="{title_info["url"]}">{title_info["title"]}</a></li>'

        episode = f'''
        <li class="episode">
        <div class="episode-content">
            <h2>Avsnitt {episode_info["Episode"]}</h2>
            <p class="meta"><strong>Publicerad:</strong> {episode_info["Date"]} |
             <strong>Längd:</strong> {episode_info["Duration"]} 
            </p>
            <p>{c.summary}</p>
            <p>I dagens avsnitt så tittar vi på dessa artiklar:</p>
            <ul>
                {included_titles_html}
            </ul>
            <p><strong>Ljudfil:</strong> <a href="{c.remote_audio_directory}{episode_info["AudioFile"]}">Ladda ned</a></p>
            <audio controls>
                <source src="{c.remote_audio_directory}{episode_info["AudioFile"]}" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
        </div>
        <img src="{c.image_url}" alt="Episode thumbnail" class="episode-thumbnail">
        </li>
        '''

        episode_list_content.append(episode)

    episode_list_content.append(html_outro)

    with open("html_web/index.html", "w") as f:
        f.write("\n".join(episode_list_content))

    print(f"\n{Colors.GREEN}HTML - ALL DONE{Colors.RESET}\n")



# Uploads files to your webserver

def upload_files():

    print(f"--- --- --- ---\n\n{Colors.GREEN}9. UPLOADING FILES TO WEB SERVER{Colors.RESET}\n")

    episode_number = len(episodes_table)
    
    try:
        host = c.host
        port = c.port
        transport = paramiko.Transport((host, port))

        password = c.password
        username = c.username
        
        transport.connect(username = username, password = password)

        sftp = paramiko.SFTPClient.from_transport(transport)

        sftp.chdir(c.remote_path)

        filepath1 = "index.html"
        localpath1 = "html_web/index.html"

        filepath2 = "style.css"
        localpath2 = "html_web/style.css"

        filepath3 = "podcast_feed.xml"
        localpath3 = "feed/podcast_feed.xml"

        filepath4 = f"audio/audio_episodes/{episode_number}_podcast_episode.mp3"
        localpath4 = f"audio_episodes/{episode_number}_podcast_episode.mp3"

        sftp.put(localpath1, filepath1)
        print("Uploaded: index.html")
        sftp.put(localpath2, filepath2)
        print("Uploaded: style.css")
        sftp.put(localpath3, filepath3)
        print("Uploaded: podcast_feed.xml")
        sftp.put(localpath4, filepath4)
        print(f"Uploaded: {episode_number}_podcast_episode.mp3")

        sftp.close()
        transport.close()
    
    except Exception as e:
        print(f"Error uploading file: {e}")
        
        pass

    print(f"\n{Colors.GREEN}FILE UPLOAD - ALL DONE{Colors.RESET}\n")



# Function to count number of unpublished articles. Used in Main function in condition
# that it will not create a new podcast episode if there are fewer than eg 7 articles.

def count_unpublished_entries():
    
    Article = Query()

    all_entries = db.search(Article.Title.exists())  # This will fetch all entries with a Title field
    
    #all_entries = db.search(Article)
    unpublished_count = 0

    for entry in all_entries:
        if not entry["Published"]:
            unpublished_count += 1

    return unpublished_count



# Main function
# All functions can be run individually. This is great for testing. So, comment out all functions except
# for the first one. Then test them until you see that all works for you.

def Main():

    # 1
    read_rss_and_find_articles()
    
    # 2
    scrape_article()   
    
    # 3
    send_to_gpt()

    ### IF MORE THAN 7 ARTICLES - CREATE NEW PODCAST EPISODE ---->

    unpublished_count = count_unpublished_entries()
    print(f"\n--- --- --- --- ---\n\nCHECKNING FOR NUMBER OF UNPUBLISHED ENTRIES: {unpublished_count}\n")

    if unpublished_count < 6:
        print("Not enough new posts for a new episode. Exiting...\n\n")
    else:
        print(f"\n--- --- --- --- ---\n\nCREATING NEW EPISODE\n\n")

        # 4
        find_text_to_convert_to_speech()

        # 5
        create_pocast_intro_and_outro()

        # 6
        mix_and_create_podcast_episode()

        # 7
        create_xml_feed()

        # 8
        create_html_feed()

        # 9
        upload_files()


if __name__ == "__main__":
    Main()






