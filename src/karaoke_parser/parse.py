import datetime
import json
import os
import re
from pathlib import Path
from typing import cast

from analyze_version import match_best
from metadata_utils.CF_Program import Song, get_all_mp3_as_obj
from metadata_utils.remuxer import remux_song
from neurokaraoke_scraper import get_last_date, get_songs_info
from thefuzz import fuzz, process

with open(Path(__file__).parent.parent.parent / "config.json") as f:
    CONFIGS = json.load(f)

RAW_SONGS_PATH = CONFIGS["RAW_SONGS_PATH"]
LATEST_ALBUM_PATH = Path(CONFIGS["LATEST_ALBUM_PATH"])
ARCHIVE_PATH = Path(CONFIGS["ARCHIVE_PATH"])
NEW_HJSON_PATH = CONFIGS["NEW_HJSON_PATH"]

def get_previous_wednesday(dt: datetime.date):
        
    # weekday(): Mon=0, Tue=1, Wed=2...
    # (current_weekday - target_weekday) % 7
    days_ago = (dt.weekday() - 2) % 7
    
    # If today is Wednesday, days_ago will be 0. 
    # If you want the *strictly* previous Wednesday (last week), 
    # you can handle that like this:
    # if days_ago == 0:
    #     days_ago = 7
        
    return str(dt - datetime.timedelta(days=days_ago))

def get_last_track(p: Path):
    ss = get_all_mp3_as_obj(p)
    return max([int(s.Track) for s in ss])

def parse_discord_file(source: Path) -> tuple[dict[str, tuple[str, str, bool]], str, str] | None:

    if not (source.exists() and source.is_file()):
        print("Source File doesn't exit!")
        return

    cover_artist_pattern = r"(\w+) Karaoke"
    date_patterns = [r"(\d{4}-\d{2}-\d{2})"]
    duet_pattern = "[Duet]"

    songs: dict[str, tuple[str, str, bool]] = {}

    with open(source, 'r', encoding='utf-8') as f:
        header = f.readline()

        cover_artist_match = re.search(cover_artist_pattern, header)

        date_match = None
        for date_pattern in date_patterns:
            date_match = re.search(date_pattern, header)
            if date_match:
                break

        date = date_match.group(1) if date_match else get_previous_wednesday(today)
        cover_artist = cover_artist_match.group(1) if cover_artist_match else "Neuro"

        for line in f:

            if line.strip() == "":
                continue

            is_duet = False
            if duet_pattern in line:
                is_duet = True
            line = line.replace(duet_pattern, "")

            title, artist = [x.strip() for x in line.split("-", 1)]

            if songs.get(title) is not None:
                print("ERROR!!! DUPLICATE TITLE!!!")

            songs[title] = (title, artist, is_duet) # Assumes unique titles, fails otherwise

    return songs, date, cover_artist

def parse_neurokaraoke() -> tuple[dict[str, tuple[str, str, bool]], str, str] | None:

    new_songs: dict[str, tuple[str, str, bool]] = {}

    songs_info = get_songs_info(get_last_date(LATEST_ALBUM_PATH) + datetime.timedelta(days=1))
    for s in songs_info:
        cover_artists = s["coverArtists"]
        is_duet = True if (',' in cover_artists or '&' in cover_artists) else False
        new_songs[s["Title"]] = (s["title"], s["originalArtists"], is_duet)

    if not songs_info:
        return 

    date = songs_info[0]["streamDate"]
    date = str(datetime.date.fromisoformat(date))

    cover_artist = songs_info[0]["coverArtists"]

    return new_songs, date, cover_artist

if __name__ == "__main__":

    today = datetime.date.today()

    DEST_LOC = Path(CONFIGS["DEST_FOLDER"]) / f"{today}_Processed"
    listing = Path(CONFIGS["LISTING_FOLDER"]) / f"{today}.txt"

    parse_result = parse_discord_file(source=listing)

    if parse_result is None:
        parse_result = parse_neurokaraoke()

    if parse_result is None:
        print("Failure parsing new data!")
        exit()

    songs, date, cover_artist = parse_result

    raw_files = get_all_mp3_as_obj(RAW_SONGS_PATH)

    archive = get_all_mp3_as_obj(ARCHIVE_PATH)

    matches: list[tuple[tuple[Song, int], tuple[str, str, bool]]] = []

    for song in songs:

        # extractOne returns (match, confidence_score)
        result = process.extractOne( # type: ignore
            song, # Song title
            raw_files, 
            processor=lambda s: s.path.stem if isinstance(s, Song) else s # type: ignore
            )
            # print(f"{raw.stem} -> {result[0]} with {result[1]}% confidence")
            
        result = cast(tuple[Song, int] | None, result)

        if result:
            matches.append((result, songs[song]))

    while len(matches) > len(raw_files): # handles re-runs of old songs
        matches.remove(min(matches, key=lambda x: x[0][1]))

    for i, match in enumerate(matches):

        song_obj = match[0][0]

        os.makedirs(DEST_LOC, exist_ok=True)

        new_path = DEST_LOC / song_obj.path.name

        remux_song(song_obj.path, new_path)
        song_obj.path = new_path
        
        xxhash = song_obj.get_hash()
        if xxhash is None:
            print(f"Error generating hash for {match}")
            continue

        song_obj.Date = date
        song_obj.Title = match[1][0]
        song_obj.Artist = match[1][1]
        song_obj.CoverArtist = "Neuro & Evil" if match[1][2] else cover_artist

        existing = match_best(
            query=song_obj, 
            scorer=fuzz.UWRatio, # type: ignore
            score_cutoff=90,
            songs=archive
            )

        if existing:
            
            previous = existing[0]

            print(f"MATCHED: {song_obj.Artist} - {song_obj.Title}")
            print(f"WITH: {previous.filename}")

            song_obj.Title = previous.Title
            song_obj.TitleOG = previous.TitleOG
            song_obj.Identify = previous.Identify
            song_obj.Artist = previous.Artist
            song_obj.ArtistOG = previous.ArtistOG

            if song_obj.CoverArtist == "Neuro" and previous.Discnumber in ("1", "2"):
                song_obj.Version = "3"
            elif song_obj.CoverArtist == "Neuro":
                if "." not in previous.Version: # previous.Version = 3
                    song_obj.Version = "3.2"
                else:
                    major_v, minor_v = previous.Version.split(".")
                    song_obj.Version = major_v + "." + str(int(minor_v) + 1) # 3.(n + 1)
            else:
                song_obj.Version = str(int(previous.Version) + 1)

            song_obj.Discnumber = "8"
            song_obj.Track = str(get_last_track(LATEST_ALBUM_PATH) + i + 1)
            song_obj.Comment = "None"
            song_obj.Special = "0"
            song_obj.xxHash = xxhash

        else:
            data: dict[str, str] = {
                "Date": date,
                "Title": match[1][0],
                "Artist": match[1][1],
                "CoverArtist": "Neuro & Evil" if match[1][2] else cover_artist,
                "Version": str(1 if (match[1][2] or cover_artist == "Evil") else 3),
                "Discnumber": "8",
                "Track": str(get_last_track(LATEST_ALBUM_PATH) + i + 1),
                "Comment": "None",
                "Special": "0",
                "xxHash": xxhash
            }
        
            song_obj.load_dict(data)

        print(song_obj.filename)

        song_obj.save()

        song_obj.set_album_image()

        song_obj.make_hjson(NEW_HJSON_PATH)

        