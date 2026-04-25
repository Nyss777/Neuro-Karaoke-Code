import csv
import json
import logging
import re
from pathlib import Path
from random import random
from time import sleep

import requests

# Lyrics are out of order 
# Lyrics are separated by new lines when JP/EN

def write_lyrics(lyrics: list[tuple[str, str]], timestamp_pattern: re.Pattern[str], xxhash: str, WORKING_DIR: Path):

    with open(WORKING_DIR / "Lyrics" / f'{xxhash}.lrc', 'w', encoding='utf-8') as l_h:
        for lyrics_line in lyrics:

            complex_timestamp = bool(re.match(timestamp_pattern, lyrics_line[0]))

            if complex_timestamp is True:
                timestamp = lyrics_line[0][3:-5]

            else:
                timestamp = lyrics_line[0]

            if '\n' not in lyrics_line[1]:
                l_h.write(f"[{timestamp}] {lyrics_line[1]}")
                l_h.write('\n')

            else:
                try:
                    jp_line, en_line = lyrics_line[1].strip().split('\n')    
                    l_h.write(f"[{timestamp}] {jp_line}")
                    l_h.write('\n')
                    l_h.write(f"[{timestamp}] {en_line}")
                    l_h.write('\n')

                except ValueError:
                    print(xxhash)
                    print(lyrics_line[1].strip().split('\n'))

def fetch_lyrics(song_id: str, session: requests.Session) -> list[dict[str, str]] | None:
    try:
        url = f"https://api.neurokaraoke.com/api/songs/{song_id}/lyrics"
        lyrics_response = session.get(url)

        lyrics_response.raise_for_status()
        
    except requests.exceptions.HTTPError as err:
        status_code = err.response.status_code if err.response is not None else "Unknown"
        logging.error(f"Http Error: {status_code}")

    except requests.exceptions.ConnectionError:
        logging.exception("Error Connecting")

    except requests.exceptions.Timeout:
        logging.exception("Timeout Error")

    except requests.exceptions.RequestException:
        logging.exception("An Error Happened")

    else:
        return lyrics_response.json()

def get_lyrics(session: requests.Session, WORKING_DIR: Path) -> None:
    
    with open(WORKING_DIR / "server_conversion.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        conversion_table: dict[str, str] = {row['UUID']: row['xxHash'] for row in reader}
            
    with open(WORKING_DIR / "full_data.jsonl", 'r', encoding='utf-8') as h:

        timestamp_pattern = re.compile(r"\d{2}:\d{2}:\d{2}\.\d{7}")

        for line in h:
            song = json.loads(line)
            
            raw_lyrics = fetch_lyrics(song_id=song["id"], session=session)

            sleep(random())

            if not raw_lyrics:
                continue

            xxhash = conversion_table[song['id']]

            sorted_lyrics = sorted([(item['time'], item['text']) for item in raw_lyrics])

            write_lyrics(sorted_lyrics, timestamp_pattern, xxhash, WORKING_DIR)