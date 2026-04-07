# import csv
import logging
import os
import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import cast

import hjson
from metadata_utils.CF_Program import get_all_mp3_as_obj

LIVE_ARCHIVE_PATH = r'C:\Users\Nyss\Downloads\Neuro Karaoke Archive'
LOCAL_REPO_LOCATION_PATH = r"C:\Users\Nyss\Documents\Code\Python\Neuro_karaoke\Metadata Sync"
BACKUP_PATH = r"C:\Users\Nyss\Downloads"


def get_all_hjson(directory: str) -> list[str]: 
    """
    Function that gathers all hjson files from a directory.
    """
    p = Path(directory)
    return [(str(f)) for f in p.rglob('*.hjson') if f.is_file()]

def get_changed_files() -> list[str]:
    # Compare ORIG_HEAD (before pull) with HEAD (after pull)
    cmd = [
        "git", "diff-tree", "-r", 
        "--no-commit-id", 
        "--name-only", 
        "ORIG_HEAD", "HEAD" 
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # filters out empty strings so you get a true empty list [] if nothing changed
    files = [f for f in result.stdout.strip().split('\n') if f]
    
    return files
    
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

    script_dir = Path(__file__).parent.absolute()

    log_path = script_dir / "logs" /f'sync_[{date.today()}].log'

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')

    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

logger = logging.getLogger(__name__)

if __name__ == "__main__":

    setup_logger()

    logger.info('-'*20 + "Program Start" + '-'*20)

    os.chdir(LOCAL_REPO_LOCATION_PATH)

    # MAIN LOOP
    # 1. Pull latest from GitHub
    subprocess.run(["git", "switch", "main"])
    subprocess.run(["git", "pull", "origin", "main"])

    changed_files = get_changed_files()
    logger.info(f"DIF-TREE RESPONSE: {changed_files}")

    if not changed_files:
        changed_files = get_all_hjson(LOCAL_REPO_LOCATION_PATH)

    logger.info(f"Number of changes: {len(changed_files)}")


    lookup_table = {metadata["xxHash"] : metadata
                    for file_path in changed_files
                    if file_path.endswith('.hjson')
                    and (metadata := get_metadata(file_path))}

    song_files = get_all_mp3_as_obj(LIVE_ARCHIVE_PATH)

    song_files_length = len(song_files)
    if song_files_length > 0:
        logger.info(f"Songs Found: {len(song_files)}")
    else:
        logger.error("No songs found! Please verify the path")

    change = False

    # with open(r"C:\Users\Nyss\Documents\Code\Python\Neuro_karaoke\hash_conversion.csv", 'r', encoding='utf-8') as f:
    #     reader = csv.DictReader(f)
    #     conversion_table = {row['Old Hash']: row['New Hash'] for row in reader}

    for song in song_files:
        
        xxhash_value = song.xxHash if song.xxHash else song.get_hash()

        if not xxhash_value:
            logger.warning(f"Unable to get xxhash for {song.path}")
            continue
        
        hjson_data = lookup_table.get(xxhash_value)

        # if hjson_data is None:
        #     hjson_data = lookup_table.get(conversion_table.get(xxhash_value,''))
        
        if not hjson_data:
            logger.warning(f"No hjson data for {song.filename}")
            continue

        copy = False
        for key, value in hjson_data.items():
            if getattr(song, key, "") != (value if isinstance(value, str) else str(value)):
                copy = True
                logger.debug(f"They differ in {key}; {getattr(song, key, "")} vs {hjson_data[key]}")

        if copy: 

            change = True
            filename = song.path.name
            parent = song.path.parent.name
            backup_song_path = Path(BACKUP_PATH) / f"Backup [{date.today()}]" / parent / filename

            os.makedirs(os.path.dirname(backup_song_path), exist_ok=True) ## side-effect
            shutil.copy2(src=song.path, dst=backup_song_path) ## side-effect

            song.load_hjson(hjson_data)
            song.save()

    change = True
    if change:

        subprocess.run(["rclone", "sync",
                        f"{LIVE_ARCHIVE_PATH}", 
                        "Nyss_ecomp:\\Neuro Karaoke Archive V3",
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
                            f"{LIVE_ARCHIVE_PATH}", 
                            "Nyss_ecomp:\\Neuro Karaoke Archive V3",
                            "--exclude", ".stfolder/**",
                            "--exclude", ".stversions/**",
                            "--fast-list",
                            "--checksum"
                            ])

        elif comfirmation == "reset":
            subprocess.run(["git", "reset", "--hard", "ORIG_HEAD"])

        else:
            print("Synchronization Cancelled!")
