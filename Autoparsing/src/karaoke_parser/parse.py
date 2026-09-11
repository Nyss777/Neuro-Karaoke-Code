import argparse
import datetime
import json
import logging
import os
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from analyze_version import match_best
from dateutil import parser
from metadata_utils.CF_Program import Song, get_all_mp3_as_obj
from metadata_utils.remuxer import remux_song
from thefuzz import fuzz, process

logger = logging.getLogger(__name__)

@dataclass
class SourceSong:
    source_title: str
    source_artist: str
    is_duet: bool
    
@dataclass
class Match:
    data_source: SourceSong
    raw_song: Song
    match_confidence: int

type SourceTitle = str
type Date = str
type CoverArtist = str

SCRIPT_FOLDER = Path(__file__).parent.parent.parent 

with open(SCRIPT_FOLDER / "config.json") as f:
    CONFIGS = json.load(f)

ARCHIVE_PATH = Path(CONFIGS["ARCHIVE_PATH"])
# Point this to the hjson repository

LOG_DIRECTORY = SCRIPT_FOLDER / "Logs"
DEST_FOLDER = SCRIPT_FOLDER / "Processed_Songs"

def fetch_from_zip(zip_path: Path) -> list[str]:
    with zipfile.ZipFile(zip_path, 'r') as zip_file:
        return zip_file.namelist()

def read_file_from_zip(zip_path: Path, file_name: str) -> bytes:
    with zipfile.ZipFile(zip_path, 'r') as zip_file:
        return zip_file.read(file_name)

def setup_logger():
    logger = logging.getLogger()

    log_path = Path(LOG_DIRECTORY) / f'[{datetime.date.today()}].log'  # noqa: DTZ011

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

def get_last_track(archive: list[Song], disc: str) -> int:
    ss: list[int] = []
    for s in archive:
        print(s.Discnumber)
        print(disc)
        if s.Discnumber == disc:
            ss.append(int(s.Track))
        
    return max(ss) if ss else 0

def get_disc_from_date(date: Date) -> str:
    if date < "2023-05-27":
        return "1"
    elif date < "2023-06-21":
        return "2"
    elif date < "2023-12-19":
        return "3"
    elif date < "2024-07-10":
        return "4"
    elif date < "2024-11-17":
        return "5"
    elif date < "2025-05-28":
        return "6"
    elif date < "2025-12-19":
        return "7"
    elif date < "2026-06-24":
        return "8"
    else:
        return "9"

def parse_discord_file(source: Path) -> tuple[
    dict[SourceTitle, SourceSong], Date, CoverArtist] | None:

    if not (source.exists() and source.is_file()):
        logger.error("Source File doesn't exit!")
        return

    cover_artist_pattern = r"(\w.+?)(?:Mini-)?Karaoke"
    date_patterns = [r"(\d{2,4}\D\d{2}\D\d{2,4})"]
    duet_pattern = "[Duet]"

    songs: dict[str, SourceSong] = {}

    with open(source, 'r', encoding='utf-8') as f:
        header = f.readline()

        cover_artist_match = re.search(cover_artist_pattern, header)

        date_match = None
        for date_pattern in date_patterns:
            date_match = re.search(date_pattern, header)
            if date_match:
                break

        if date_match is None:
            date = get_previous_wednesday(datetime.date.today())  # noqa: DTZ011
            logger.warning(f"No date found in listing, using default: {date}")
        else:
            try:
                date_string = date_match.group(1)
                date = str(parser.parse(date_string, dayfirst=True).date())
            except ValueError:
                date = get_previous_wednesday(datetime.date.today())  # noqa: DTZ011
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
            songs[title] = SourceSong(source_title=title, source_artist=artist, is_duet=is_duet) 

    return songs, date, cover_artist

if __name__ == "__main__":

    setup_logger()

    logger.info('-'*20 + "Program Start" + '-'*20)

    arg_parser = argparse.ArgumentParser(description='')

    arg_parser.add_argument('--listing', '-l', type=str, required=True, 
        help='Karaoke Songs Listing Path')
    arg_parser.add_argument('--raw-folder', '-r', type=str, required=True, 
        help='Karaoke Songs Folder/Zip Path')

    args = arg_parser.parse_args()

    listing = Path(args.listing).expanduser()

    parse_result = parse_discord_file(source=listing)

    if parse_result is None:
        logger.error("Failure parsing new data!")
        sys.exit()

    songs, date, cover_artist = parse_result

    dest_loc = DEST_FOLDER / f"Karaoke_[{date}]"

    raw_source = Path(args.raw_folder).expanduser()

    if Path(args.raw_folder).suffix == '.zip':
        raw_files = [
            Song(s, allow_fake_path=True) 
            for s in fetch_from_zip(raw_source)
            ]
    else:
        raw_files = get_all_mp3_as_obj(raw_source)

    if not raw_files:
        logger.error("No audio files found.")
        sys.exit()

    archive = [(Song(f, allow_incompatible=True)) for f in ARCHIVE_PATH.rglob('*.hjson') if f.is_file()]

    last_track = get_last_track(archive, get_disc_from_date(date))
    
    matches: list[Match] = []

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
            matches.append(
                Match(
                raw_song=result[0], 
                match_confidence=result[1], 
                data_source=songs[song]
                ))

    while len(matches) > len(raw_files): # handles re-runs of old songs
        logger.debug(f"Removing {min(matches, key=lambda x: x.match_confidence)}")
        matches.remove(min(matches, key=lambda x: x.match_confidence))

    for i, match in enumerate(matches):

        song_obj = match.raw_song

        os.makedirs(dest_loc, exist_ok=True)

        new_path = dest_loc / song_obj.path.name

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
        song_obj.Title = match.data_source.source_title
        song_obj.Artist = match.data_source.source_artist
        song_obj.CoverArtist = "Neuro & Evil" if match.data_source.is_duet else cover_artist

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

            song_obj.Discnumber = get_disc_from_date(date)
            song_obj.Track = str(last_track + i + 1)
            song_obj.Comment = "None"
            song_obj.Special = "0"
            song_obj.xxHash = xxhash

        else:
            data: dict[str, str] = {
                "Date": date,
                "Title": match.data_source.source_title,
                "Artist": match.data_source.source_artist,
                "CoverArtist": "Neuro & Evil" if match.data_source.is_duet else cover_artist,
                "Version": str(1 if (match.data_source.is_duet or cover_artist == "Evil") else 3),
                "Discnumber": get_disc_from_date(date),
                "Track": str(last_track + i + 1),
                "Comment": "None",
                "Special": "0",
                "xxHash": xxhash
            }
        
            song_obj.load_dict(data)

        logger.info(f"Processed: {song_obj.filename}")

        song_obj.save()

        song_obj.set_album_image()

        song_obj.make_hjson(ARCHIVE_PATH)

        
