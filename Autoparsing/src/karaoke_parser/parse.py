import argparse
import datetime
import json
import logging
import os
import re
import zipfile
from pathlib import Path
from typing import Text, cast

from analyze_version import match_best
from dateutil import parser
from metadata_utils.CF_Program import Song, get_all_mp3_as_obj
from metadata_utils.remuxer import remux_song
from thefuzz import fuzz, process

logger = logging.getLogger(__name__)

with open(Path(__file__).parent.parent.parent / "config.json") as f:
    CONFIGS = json.load(f)

RAW_SONGS_FOLDER = CONFIGS["RAW_SONGS_FOLDER"]
LATEST_ALBUM_PATH = Path(CONFIGS["LATEST_ALBUM_PATH"])
ARCHIVE_PATH = Path(CONFIGS["ARCHIVE_PATH"])
NEW_HJSON_PATH = CONFIGS["NEW_HJSON_PATH"]
LOG_DIRECTORY = CONFIGS["LOG_DIRECTORY"]

def fetch_from_zip(zip_path: Path) -> list[Text]:
    with zipfile.ZipFile(zip_path, 'r') as zip_file:
        return zip_file.namelist()

def read_file_from_zip(zip_path: Path, file_name: str) -> bytes:
    with zipfile.ZipFile(zip_path, 'r') as zip_file:
        return zip_file.read(file_name)

def setup_logger():
    logger = logging.getLogger()

    log_path = Path(LOG_DIRECTORY) / f'[{datetime.date.today()}].log'

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')

    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

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
    if not ss:
        return 0

    return max([int(s.Track) for s in ss])

def parse_discord_file(source: Path) -> tuple[dict[str, tuple[str, str, bool]], str, str] | None:

    if not (source.exists() and source.is_file()):
        logger.error("Source File doesn't exit!")
        return

    cover_artist_pattern = r"(\w.+?)(?:Mini-)?Karaoke"
    date_patterns = [r"(\d{2,4}\D\d{2}\D\d{2,4})"]
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

        if date_match is None:
            date = get_previous_wednesday(datetime.date.today())
            logger.warning(f"No date found in listing, using default: {date}")
        else:
            try:
                date_string = date_match.group(1)
                date = str(parser.parse(date_string, dayfirst=True).date())
            except ValueError:
                date = get_previous_wednesday(datetime.date.today())
                logger.warning(f"No date found in listing, using default: {date}")


        if cover_artist_match:
            cover_artist = cover_artist_match.group(1).strip()
        else:
            cover_artist = "Neuro"

        if not cover_artist_match:
            logger.warning(
                "No cover artist found in listing, using default: Neuro"
                )

        if cover_artist.title() == "Evil Neuro":
            cover_artist = "Evil"

        for line in f:

            if line.strip() == "":
                continue

            is_duet = False
            if duet_pattern in line:
                is_duet = True
            line = line.replace(duet_pattern, "")

            title, artist = [x.strip() for x in line.split(" - ", 1)]
            if line.count("-") > 1:
                logger.warning("multiple \"-\" found, possible parser failure.")

            if songs.get(title) is not None:
                logger.error("ERROR!!! DUPLICATE TITLE!!!")

            # Assumes unique titles, fails otherwise
            songs[title] = (title, artist, is_duet) 

    return songs, date, cover_artist

if __name__ == "__main__":

    setup_logger()

    logger.info('-'*20 + "Program Start" + '-'*20)

    arg_parser = argparse.ArgumentParser(description='')

    arg_parser.add_argument('--listing', '-l', type=str, required=True, 
        help='Karaoke Songs Listing Path')
    arg_parser.add_argument('--raw-folder', '-r', type=str, required=True, 
        help='Karaoke Songs Folder Path')

    args = arg_parser.parse_args()

    listing = Path(CONFIGS["LISTING_FOLDER"]) / args.listing

    parse_result = parse_discord_file(source=listing)

    if parse_result is None:
        logger.error("Failure parsing new data!")
        exit()

    songs, date, cover_artist = parse_result

    DEST_LOC = Path(CONFIGS["DEST_FOLDER"]) / f"{date}_Processed"

    raw_source = Path(RAW_SONGS_FOLDER) / Path(args.raw_folder).name

    if Path(args.raw_folder).suffix == '.zip':
        raw_files = [
            Song(s, allow_fake_path=True) 
            for s in fetch_from_zip(raw_source)
            ]
    else:
        raw_files = get_all_mp3_as_obj(raw_source)

    if not raw_files:
        logger.error("No audio files found.")
        exit()

    archive = get_all_mp3_as_obj(ARCHIVE_PATH)

    matches: list[tuple[tuple[Song, int], tuple[str, str, bool]]] = []

    for song in songs:

        # extractOne returns (match, confidence_score)
        result = process.extractOne( # type: ignore
            song, # Song title
            raw_files, 
            processor=lambda s: s.path.stem if isinstance(s, Song) else s # type: ignore
            )
        
        logger.debug(f"{song} -> {result[0]} with {result[1]}% confidence")
            
        result = cast(tuple[Song, int] | None, result)

        if result:
            matches.append((result, songs[song]))

    while len(matches) > len(raw_files): # handles re-runs of old songs
        logger.debug(f"Removing {min(matches, key=lambda x: x[0][1])}")
        matches.remove(min(matches, key=lambda x: x[0][1]))

    for i, match in enumerate(matches):

        song_obj = match[0][0]

        os.makedirs(DEST_LOC, exist_ok=True)

        new_path = DEST_LOC / song_obj.path.name

        if Path(args.raw_folder).suffix == '.zip':
            remux_song(
                read_file_from_zip(raw_source, song_obj.path.name), 
                new_path
                )
        else:
            remux_song(song_obj.path, new_path)

        song_obj.path = new_path
        
        xxhash = song_obj.get_hash()
        if xxhash is None:
            logger.error(f"Error generating hash for {match}")
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

            logger.debug(f"MATCHED: {song_obj.Artist} - {song_obj.Title}")
            logger.debug(f"WITH: {previous.filename}")

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

            song_obj.Discnumber = "9"
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
                "Discnumber": "9",
                "Track": str(get_last_track(LATEST_ALBUM_PATH) + i + 1),
                "Comment": "None",
                "Special": "0",
                "xxHash": xxhash
            }
        
            song_obj.load_dict(data)

        logger.info(f"Processed: {song_obj.filename}")

        song_obj.save()

        song_obj.set_album_image()

        song_obj.make_hjson(NEW_HJSON_PATH)

        