import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from metadata_utils.CF_Program import Song, get_all_mp3_as_obj
from remuxer import remux_song
from thefuzz import process


def get_previous_wednesday(dt: datetime | None = None):
    if dt is None:
        dt = datetime.now()
        
    # weekday(): Mon=0, Tue=1, Wed=2...
    # (current_weekday - target_weekday) % 7
    days_ago = (dt.weekday() - 2) % 7
    
    # If today is Wednesday, days_ago will be 0. 
    # If you want the *strictly* previous Wednesday (last week), 
    # you can handle that like this:
    # if days_ago == 0:
    #     days_ago = 7
        
    return dt - timedelta(days=days_ago)

# Example usage:
print(get_previous_wednesday().strftime("%Y-%m-%d"))

listing = r"C:\Users\Nyss\Documents\Code\Python\Neuro_karaoke\Autoparsing\2026-03-26.txt"
image_file_path = r'C:\Users\Nyss\Downloads\Neuro Karaoke Archive\Extra Content\Resized Cover Art\Disc 8 cover art by lukuwo.jpg'

cover_artist_pattern = r"(\w+) Karaoke"
date_patterns = [r"(\d{4}-\d{2}-\d{2})"]
# date_patterns = [r"(\d{4}-\d{2}-\d{2})", r"(\d{2}/\d{2}/\d{4})"]
duet_pattern = "[Duet]"

songs: list[dict[str, tuple[str, str, bool]]] = []

raw_songs = r"C:\Users\Nyss\Downloads\01 04 26 neuro karaoke"

last_track = 133

#DEST_LOC = Path(r"C:\Users\Nyss\Downloads\Neuro Karaoke Archive\DISC 8 - Third Anniversary (2025-12-19 - Present)")
DEST_LOC = Path(r"C:\Users\Nyss\Downloads\2026-03-26_Processed")

with open(listing, 'r', encoding='utf-8') as f:
    header = f.readline()

    cover_artist_match = re.search(cover_artist_pattern, header)

    date_match = None
    for date_pattern in date_patterns:
        date_match = re.search(date_pattern, header)
        if date_match:
            break

    date = date_match.group(1) if date_match else get_previous_wednesday().strftime("%Y-%m-%d")
    cover_artist = cover_artist_match.group(1) if cover_artist_match else "Neuro"

    for line in f:

        if line.strip() == "":
            continue

        is_duet = False
        if duet_pattern in line:
            is_duet = True
        line = line.replace(duet_pattern, "")

        title, artist = [x.strip() for x in line.split("-", 1)]

        songs.append({title : (title, artist, is_duet)})


raw_files = get_all_mp3_as_obj(raw_songs)

matches: list[tuple[Song, tuple[str, str, bool]]] = []

# for raw in raw_files:
#     # extractOne returns (match, confidence_score)
#     result = process.extractOne(raw.stem, songs)
#     # print(f"{raw.stem} -> {result[0]} with {result[1]}% confidence")
#     if result:
#         (inner_tuple,) = result[0].values()
#         matches.append((raw, inner_tuple))

for song in songs:
    # extractOne returns (match, confidence_score)
    result = process.extractOne(list(song.keys())[0], [raw.path.stem for raw in raw_files])
    # print(f"{raw.stem} -> {result[0]} with {result[1]}% confidence")
    if result:
        (inner_tuple,) = song.values()
        matches.append(([x for x in raw_files if x.path.stem == result[0]][0], inner_tuple))

print(matches)

image_data = None
with open(image_file_path, 'rb') as albumart:
        image_data = albumart.read()

for i, match in enumerate(matches):

    song_obj = Song(match[0])

    os.makedirs(DEST_LOC, exist_ok=True)

    new_path = DEST_LOC / song_obj.path.name

    remux_song(song_obj.path, new_path)
    
    xxhash = get_path_hash(match[0])
    if xxhash is None:
        print(f"Error generating hash for {match}")
        continue


    data: dict[str, str | int | float] = {
        "Date": date,
        "Title": match[1][0],
        "Artist": match[1][1],
        "CoverArtist": "Neuro & Evil" if match[1][2] else cover_artist,
        "Version": 1 if (match[1][2] or cover_artist == "Evil") else 3,
        "Discnumber": 8,
        "Track": last_track + i + 1,
        "Comment": "None",
        "Special": 0,
        "xxHash": xxhash
    }
    payload = create_payload_from_dict(data, str(match[0]))

    process_new_tags(song_obj, {k : v if isinstance(v, str) else f"{v}" for k, v in data.items()})

    set_tags(str(new_path), song_obj, "jpeg", image_data)

    engrave_payload(path=new_path, song_data=payload)


    print(song_obj.filename)

    # if Path(song_obj.filename).exists():
    #     Path(song_obj.filename).unlink()
    #     print("File deleted successfully.")
    # else: 
    #     print("doesnt exist")

    os.rename(DEST_LOC / song_obj.path.name, DEST_LOC / song_obj.filename)