import json
import logging
import os
import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import cast

import hjson
from metadata_utils.CF_Program import Song, get_all_mp3_as_obj

logger = logging.getLogger(__name__)

with open(Path(__file__).parent.parent.parent / "config.json") as f:
    CONFIGS = json.load(f)

ARCHIVE_PATH = CONFIGS["ARCHIVE_PATH"]
ARCHIVE_METADATA = CONFIGS["ARCHIVE_METADATA"]
BACKUP_PATH = Path(CONFIGS["BACKUP_PATH"])
LOG_DIR = Path(CONFIGS["LOG_PATH"])
REMOTE_NAME = CONFIGS["REMOTE_NAME"]
REMOTE_ARCHIVE_FOLDER = CONFIGS["REMOTE_ARCHIVE_FOLDER"]


def get_all_hjson(directory: str) -> list[str]: 
    """
    Function that gathers all hjson files from a directory.
    """
    p = Path(directory)
    return [(str(f)) for f in p.rglob('*.hjson') if f.is_file()]
    
def get_metadata(hjson_path: str) -> ( dict[str, str|int|float] | None ):
    # 1. Load the HJSON metadata
    try:
        with open(hjson_path, 'r', encoding='utf-8') as f:
            metadata = cast(dict[str, (str | int | float)], hjson.load(f))
        return metadata

    except Exception as e:
        print(f"Unable to process metadata for {os.path.basename(hjson_path)}!")
        print(e)
        return None

def setup_logger():
    logger = logging.getLogger()

    log_path = LOG_DIR / f'sync_[{date.today()}].log'

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')

    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

FIELD_DEFAULTS = {
                "Special": "0"
            }


if __name__ == "__main__":

    setup_logger()

    logger.info('-'*20 + "Program Start" + '-'*20)

    os.chdir(ARCHIVE_METADATA)

    subprocess.run(["git", "switch", "main"])

    changed_files = get_all_hjson(ARCHIVE_METADATA)

    logger.info(f"Number of changes: {len(changed_files)}")

    lookup_table = {metadata["xxHash"] : metadata
                    for file_path in changed_files
                    if file_path.endswith('.hjson')
                    and (metadata := get_metadata(file_path))}

    song_files = get_all_mp3_as_obj(ARCHIVE_PATH)

    song_files_length = len(song_files)
    if song_files_length > 0:
        logger.info(f"Songs Found: {len(song_files)}")
    else:
        logger.error("No songs found! Please verify the path")

    change = False

    for song in song_files:
        
        xxhash_value = song.xxHash if song.xxHash else song.get_hash()

        if not xxhash_value:
            logger.warning(f"Unable to get xxhash for {song.path}")
            continue
        
        hjson_data = lookup_table.get(xxhash_value)
        
        if not hjson_data:
            logger.warning(f"No hjson data for {song.filename} - {xxhash_value}")
            continue

        copy = False

        for field in Song.FIELDS:
            value = hjson_data.get(field, FIELD_DEFAULTS.get(field, ""))
            if getattr(song, field, "") != (value if isinstance(value, str) else str(value)):
                copy = False
                logger.debug(f"They differ in {field}; {getattr(song, field, "")} vs {value}")

            
        if copy: 

            change = True
            filename = song.path.name
            parent = song.path.parent.name
            backup_song_path = BACKUP_PATH / f"Backup [{date.today()}]" / parent / filename

            os.makedirs(os.path.dirname(backup_song_path), exist_ok=True) ## side-effect
            shutil.copy2(src=song.path, dst=backup_song_path) ## side-effect

            song.load_hjson(hjson_data)
            song.save()

    change = True
    if change:

        subprocess.run(["rclone", "sync",
                        f"{ARCHIVE_PATH}", 
                        f"{REMOTE_NAME}:\\{REMOTE_ARCHIVE_FOLDER}",
                        "--exclude", ".stfolder/**",
                        "--exclude", ".stversions/**",
                        "--dry-run",
                        "--combined",
                        "--fast-list",
                        "--checksum"
                        ])

        comfirmation = input("Type 'commit' to accept: \n")

        if comfirmation == 'commit':
            subprocess.run(["rclone", "sync","-P",
                            f"{ARCHIVE_PATH}", 
                            F"{REMOTE_NAME}:\\{REMOTE_ARCHIVE_FOLDER}",
                            "--exclude", ".stfolder/**",
                            "--exclude", ".stversions/**",
                            "--fast-list",
                            "--checksum"
                            ])

        elif comfirmation == "reset":
            subprocess.run(["git", "reset", "--hard", "ORIG_HEAD"])

        else:
            print("Synchronization Cancelled!")
