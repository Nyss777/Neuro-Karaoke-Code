import datetime
import os
import re
from pathlib import Path

from metadata_utils.CF_Program import Song, get_all_mp3_as_obj
from remuxer import remux_song
from thefuzz import process

from neurokaraoke_scraper import get_last_date, get_songs_info

RAW_SONGS_PATH = r"C:\Users\Nyss\Downloads\01 04 26 neuro karaoke"
IMAGE_FILE_PATH = r'C:\Users\Nyss\Downloads\Neuro Karaoke Archive\Extra Content\Resized Cover Art\Disc 8 cover art by lukuwo.jpg'
LATEST_ALBUM_PATH = Path(r"C:\Users\Nyss\Downloads\Neuro Karaoke Archive\DISC 8 - Third Anniversary (2025-12-19 - Present)")
NEW_HJSON_PATH = r"C:\Users\Nyss\Documents\Code\Python\Neuro_karaoke\Metadata Sync\DISC 8 - Third Anniversary (2025-12-19 - Present)"

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
        new_songs[s["Title"]] = (s["title"], s["artist"], is_duet)

    if not songs_info:
        return 

    date = songs_info[0]["streamDate"]
    date = str(datetime.date.fromisoformat(date))

    cover_artist = songs_info[0]["coverArtists"]

    return new_songs, date, cover_artist

if __name__ == "__main__":

    today = datetime.date.today()
    with open(IMAGE_FILE_PATH, 'rb') as albumart:
            image_data = albumart.read()

    #DEST_LOC = Path(r"C:\Users\Nyss\Downloads\Neuro Karaoke Archive\DISC 8 - Third Anniversary (2025-12-19 - Present)")
    DEST_LOC = Path(f"C:\\Users\\Nyss\\Downloads\\{today}_Processed")

    listing = Path(f"C:\\Users\\Nyss\\Documents\\Code\\Python\\Neuro_karaoke\\Autoparsing\\{today}.txt")

    parse_result = parse_discord_file(source=listing)

    if parse_result is None:
        parse_result = parse_neurokaraoke()

    if parse_result is None:
        print("Failure parsing new data!")
        exit()

    songs, date, cover_artist = parse_result

    raw_files = get_all_mp3_as_obj(RAW_SONGS_PATH)

    matches: list[tuple[Song, tuple[str, str, bool]]] = []

    for song in songs:

        result = process.extractOne(  # extractOne returns (match, confidence_score)
            song, # Song title
            raw_files, 
            processor=lambda s: s.path.stem
            )
            # print(f"{raw.stem} -> {result[0]} with {result[1]}% confidence")
            
        if result:
            matches.append((result[0], songs[song]))

    for i, match in enumerate(matches):

        song_obj = match[0]

        os.makedirs(DEST_LOC, exist_ok=True)

        new_path = DEST_LOC / song_obj.path.name

        remux_song(song_obj.path, new_path)
        song_obj.path = new_path
        
        xxhash = song_obj.get_hash()
        if xxhash is None:
            print(f"Error generating hash for {match}")
            continue

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
        
        song_obj._load_dict(data)

        print(song_obj.filename)

        song_obj.save()

        song_obj.make_hjson(NEW_HJSON_PATH)

        