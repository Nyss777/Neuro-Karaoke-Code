import logging
import os
import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import cast

import hjson
from CF_Program import Song, get_song_data, process_new_tags, set_tags
from create_hjsons import create_payload_from_dict
from engraver import engrave_payload, get_all_mp3
from hash_mutagen import get_audio_hash

LIVE_ARCHIVE_PATH = r'C:\Users\Nyss\Downloads\Neuro Karaoke Archive\Neuro Karaoke Archive'
LOCAL_REPO_LOCATION_PATH = r"C:\Users\Nyss\Documents\Code\Metadata Sync"
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

    except Exception:
        print(f"Unable to process metadata for {os.path.basename(hjson_path)}!")
        return None

def setup_logger():
    logger = logging.getLogger()

    script_dir = Path(__file__).parent.absolute()

    log_path = script_dir / f'sync [{date.today()}].log'

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')

    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger

logger = logging.getLogger(__name__)

if __name__ == "__main__":

    setup_logger()

    logger.info('-'*20 + "Program Start" + '-'*20)

    os.chdir(LOCAL_REPO_LOCATION_PATH)

    # MAIN LOOP
    # 1. Pull latest from GitHub
    # subprocess.run(["git", "pull", "origin", "main"])

    # changed_files = get_changed_files()
    # logger.info(f"Number of changes: {len(changed_files)}")
    # logger.info(f"DIF-TREE RESPONSE: {changed_files}")

    ## PLACEHOLDER
    changed_files = get_all_hjson(LOCAL_REPO_LOCATION_PATH)

    lookup_table = {metadata["xxHash"] : metadata
                    for file_path in changed_files
                    if file_path.endswith('.hjson')
                    and (metadata := get_metadata(file_path))}

    song_files = get_all_mp3(LIVE_ARCHIVE_PATH)

    song_files_length = len(song_files)
    if song_files_length > 0:
        logger.info(f"Songs Found: {len(song_files)}")
    else:
        logger.warning("No songs found! Please verify the path")

    change = False
    for song_path in song_files:
        payload, song_data, _ = get_song_data(song_path)

        xxhash_value = song_data.get("xxHash", None) ## If this is too slow maybe use regex on the payload

        if not xxhash_value:
            xxhash_value = get_audio_hash(song_path)
        if not xxhash_value:
            logger.warning(f"Unable to get xxhash for {song_path}")
            continue
        
        hjson_data = lookup_table.get(xxhash_value)

        if not hjson_data:
            continue
        
        copy = False
        for key in hjson_data:
            if song_data[key] != str(hjson_data[key]): # Add safe .get() here
                copy = True
                logger.debug(f"They differ in {key}; {song_data[key]} vs {hjson_data[key]}")

        if copy: 
            change = True
            filename = os.path.basename(song_path)
            parent = os.path.basename(os.path.dirname(song_path))
            backup_song_path = os.path.join(BACKUP_PATH, f"Backup [{date.today()}]", parent, filename)

            os.makedirs(os.path.dirname(backup_song_path), exist_ok=True) ## side-effect
            shutil.copy2(src=song_path, dst=backup_song_path) ## side-effect

            new_payload = create_payload_from_dict(hjson_data=hjson_data, song_path=song_path, filename=filename)
            engrave_payload(path=song_path, song_data=new_payload) ## side-effect

            song_obj = Song(song_path)
            process_new_tags(song_obj)

            set_tags(song_path, song_obj, None, None) ## side-effect

            if song_obj.filename != os.path.basename(song_path):
                renamed_path = os.path.join(os.path.dirname(song_path), song_obj.filename)
                os.rename(src=song_path, dst=renamed_path) ## side-effect


    # if change:
    #     subprocess.run(["rclone", "sync",
    #                     f"{LIVE_ARCHIVE_PATH}", 
    #                     "Nyss_ecomp:\\Neuro Karaoke Archive V3",
    #                     "--dry-run", "--fast-list", "--checksum" ])
    #     comfirmation = input("Type 'commit' to accept: \n")
    #     if comfirmation == 'commit':
    #         subprocess.run(["rclone", "sync",
    #                     f"{LIVE_ARCHIVE_PATH}", 
    #                     "Nyss_ecomp:\\Neuro Karaoke Archive V3",
    #                     "--fast-list", "--checksum" ])
    #     else:
    #         print("Synchronization Cancelled!")
