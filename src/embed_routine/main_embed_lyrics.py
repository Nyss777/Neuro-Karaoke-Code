import json
from pathlib import Path

import requests
from get_lyrics import get_lyrics
from get_uuid import get_uuids
from metadata_utils.CF_Program import get_all_mp3_as_obj
from update_conversion_table import update_conversion_table

WORKING_DIR = Path(__file__).parent.parent.parent

with open(WORKING_DIR / "config.json") as f:
    CONFIGS = json.load(f)

LYRICS_FOLDER = WORKING_DIR / "Lyrics"
ARCHIVE_PATH = CONFIGS["ARCHIVE_PATH"]

def get_all_lrc(p: Path | str) -> list[Path]: 
    """
    Function that gathers all LRC files from a directory.
    """
    p = Path(p)
    return [f for f in p.rglob('*.lrc') if f.is_file()]

HEADERS = {
    "User-Agent": CONFIGS["USER_AGENT"],
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://neurokaraoke.com/",
    "content-type": "application/json; charset=utf-8",
    "Origin": "https://neurokaraoke.com",
    "DNT": "1",
    "Sec-GPC": "1",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Priority": "u=4",
    "TE": "trailers"
}

if __name__ == "__main__":

    with requests.Session() as session:
        session.headers.update(HEADERS)

        get_uuids(WORKING_DIR, session)

        update_conversion_table(WORKING_DIR, session)

        get_lyrics(WORKING_DIR, session)

    lyrics_files = get_all_lrc(LYRICS_FOLDER)
    lenght = len(lyrics_files)

    song_files = {song.xxHash : song for song in get_all_mp3_as_obj(ARCHIVE_PATH)}

    fails: list[str] = []

    for i, lyric in enumerate(lyrics_files):
        song = song_files.get(lyric.stem)
        if song is None:
            fails.append(lyric.stem)
            continue
        
        print(f"{i+1}/{lenght}", end='\r', flush=True)
        song.embed_lyrics(lyric)

    with open(WORKING_DIR / "lookup_failures.txt", 'w', encoding='utf-8') as ff:
        for f in fails:
            ff.write(f + '\n')