import csv
import json
import random
import time
from pathlib import Path

from metadata_utils.CF_Program import get_audio_hash
from requests import Session


def get_remote_audio_segment_hash(abs_path: str, session: Session) -> str | None:
    # 1. Get the total file size without downloading the body
    url = "https://storage.neurokaraoke.com/" + abs_path

    try:
        response = session.get(url)

    except Exception as e:
        print(e)
        return None

    file_size = int(response.headers.get('Content-Length', 0))

    if file_size == 0:
        print("fuck")
        return None

    # 2. Determine if there is an ID3v1 tag (the 'TAG' footer)
    # We need the last 128 bytes to check for 'TAG'

    return get_audio_hash(response.content, file_size)

def update_conversion_table(session: Session, WORKING_DIR: Path):

    with open(WORKING_DIR / "server_conversion.csv", 'r+', encoding='utf-8', newline='') as f:

        reader = csv.DictReader(f)
        writer = csv.writer(f)

        conversion_set: set[str] = {row['UUID'] for row in reader}

        with open(WORKING_DIR / "full_data.jsonl", 'r', encoding='utf-8') as h:

            for line in h:
                song = json.loads(line)
                
                if song['id'] not in conversion_set:

                    xxhash = get_remote_audio_segment_hash(song["absolutePath"], session=session)

                    writer.writerow([song["id"], xxhash])

                    time.sleep(random.random()*2)     

