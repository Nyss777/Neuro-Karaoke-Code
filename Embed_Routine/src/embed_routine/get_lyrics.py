import csv
import json
import logging
import re
from pathlib import Path
from random import random
from time import sleep

import requests
from metadata_utils.CF_Program import Song
from metadata_utils.embed_lyrics import get_embedded_lyrics

# Lyrics are out of order 
# Lyrics are separated by new lines when JP/EN

timestamp_pattern = re.compile(r"\d{2}:\d{2}:\d{2}\.\d{7}")

def write_lyrics(lyrics: list[tuple[str, str]], xxhash: str, WORKING_DIR: Path):

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

def get_lyrics(
    WORKING_DIR: Path, 
    session: requests.Session, 
    song_files: dict[str, Song], 
    skip_existing: bool
    ) -> None:
    
    with open(WORKING_DIR / "server_conversion.csv", encoding='utf-8') as f:
        reader = csv.DictReader(f)
        conversion_table: dict[str, str] = {row['UUID']: row['xxHash'] for row in reader}
    
    with open(WORKING_DIR / "compatibility_hashes.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        compatibility_table: dict[str, str] = {row['UUID']: row['Compatibility xxHash'] for row in reader}

    for c_hash, c_value in compatibility_table.items():
        conversion_table[c_hash] = c_value

    with open(WORKING_DIR / "uuid.jsonl", 'r', encoding='utf-8') as h:

        total_count = sum(1 for _ in h)
        h.seek(0)

        for i, line in enumerate(h):
            remote_song = json.loads(line)

            xxhash = conversion_table[remote_song['id']]

            local_song = song_files.get(xxhash)
            if local_song is None:
                print("Song not found for hash:", xxhash)
                print(remote_song['id'])
                continue

            if any(get_embedded_lyrics(local_song.path)) and skip_existing:
                continue

            raw_lyrics = fetch_lyrics(song_id=remote_song["id"], session=session)

            sleep(random())

            if not raw_lyrics:
                continue

            sorted_lyrics = sorted([(item['time'], item['text']) for item in raw_lyrics])

            write_lyrics(sorted_lyrics, xxhash, WORKING_DIR)
            
            print(f"{i+1}/{total_count}", xxhash)