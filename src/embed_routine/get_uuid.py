import json
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

# --- Usage ---

url = "https://api.neurokaraoke.com/api/songs"

# The headers based on your network trace

payload: dict[str, Any] = {
    "search": None,
    "page": 0,
    "pageSize": 2000,
    "sortBy": "KaraokeDate",
    "sortDesc": True,
    "genreIds": None,
    "themeIds": None,
    "moodIds": None,
    "artistIds": None,
    "coverArtistIds": None,
    "energyLevel": None,
    "tempo": None,
    "key": None,
    "karaokeStart": None,
    "karaokeEnd": None
}

def get_uuids(session: requests.Session) -> None:        
    
    UUID_LOCATION = Path(r"C:\Users\Nyss\Documents\Code\Python\Neuro_karaoke\Embed Routine")
    BACKUP_LOCATION = UUID_LOCATION / "backup"

    # Sending the POST request
    response = session.post(url, json=payload)

    # dict_keys(['id', 'title', 'absolutePath', 'playCount', 'duration', 'streamDate', 'dateAdded', 'coverArtists', 'originalArtists', 'genres', 'coverArt', 'thumbnailArt', 'order', 'hasLyrics', 'userUploaded', 'videoId'])

    if response.status_code == 200 or response.status_code == 201:

        try:
            data = response.json()
            
            if (old_uuid := UUID_LOCATION / 'uuid.jsonl').is_file():
                timestamp = datetime.today().strftime('%Y-%m-%d_%H-%M-%S')
                new_name = f"uuid [{timestamp}].jsonl"
                old_uuid.replace(BACKUP_LOCATION / new_name)

            with open(UUID_LOCATION / 'uuid.jsonl', 'w', encoding='utf-8') as f:
                for entry in data["items"]:
                    json.dump(entry, f)
                    f.write('\n')

        except Exception as e:
            print(e)

    else:
        print(f"Failed with status code: {response.status_code}")
        print(response.text)

if __name__ == "__main__" :
    session = requests.Session()
    get_uuids(session)