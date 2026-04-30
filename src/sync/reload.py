import json
from pathlib import Path

from metadata_utils.CF_Program import get_all_mp3_as_obj

with open(Path(__file__).parent.parent.parent / "config.json") as f:
    CONFIGS = json.load(f)

ARCHIVE_PATH = CONFIGS["ARCHIVE_PATH"]

for song in get_all_mp3_as_obj(ARCHIVE_PATH):
    if song.xxHash:
        song.set_album_image()
        song.save()

