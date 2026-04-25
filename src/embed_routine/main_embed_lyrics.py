from pathlib import Path

import requests
from get_lyrics import get_lyrics
from get_uuid import get_uuids

# from get_data_by_uuid import get_full_data
from metadata_utils.CF_Program import get_all_mp3_as_obj
from update_conversion_table import update_conversion_table


def get_all_lrc(p: Path | str) -> list[Path]: 
    """
    Function that gathers all LRC files from a directory.
    """
    p = Path(p)
    return [f for f in p.rglob('*.lrc') if f.is_file()]

HEADERS = {
    "User-Agent": "NeuroKaraokeArchive/1.0 (Contact: nycolasstrauss@ecomp.ufsm.br, Discord: nyss_7)",
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
    WORKING_DIR = Path(r"C:\Users\Nyss\Documents\Code\Python\Neuro_karaoke\Embed Routine")
    LYRICS_FOLDER = r"C:\Users\Nyss\Documents\Code\Python\Neuro_karaoke\Embed Routine\Lyrics"
    SONGS_FOLDER = r"C:\Users\Nyss\Downloads\Neuro Karaoke Archive"

    with requests.Session() as session:
        session.headers.update(HEADERS)

        get_uuids(session)

        update_conversion_table(session, WORKING_DIR)

        get_lyrics(session, WORKING_DIR)

    lyrics_files = get_all_lrc(LYRICS_FOLDER)
    lenght = len(lyrics_files)

    song_files = {song.xxHash : song for song in get_all_mp3_as_obj(SONGS_FOLDER)}

    fails: list[str] = []

    for i, lyric in enumerate(lyrics_files):
        song = song_files.get(lyric.stem)
        if song is None:
            fails.append(lyric.stem)
            continue
        
        print(f"{i+1}/{lenght}", end='\r', flush=True)
        song.embed_lyrics(lyric)

    with open("lookup_failures.txt", 'w', encoding='utf-8') as ff:
        for f in fails:
            ff.write(f + '\n')