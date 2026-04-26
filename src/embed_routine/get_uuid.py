import json
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

url = "https://api.neurokaraoke.com/api/songs"

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

def get_uuids(Download_location: Path, session: requests.Session) -> None:        
    
    Backup_location = Download_location / "backup"

    response = session.post(url, json=payload)

    if response.status_code == 200 or response.status_code == 201:

        try:
            data = response.json()
            
            if (old_uuid := Download_location / 'uuid.jsonl').is_file():
                timestamp = datetime.today().strftime('%Y-%m-%d_%H-%M-%S')
                new_name = f"uuid [{timestamp}].jsonl"
                old_uuid.replace(Backup_location / new_name)

            with open(Download_location / 'uuid.jsonl', 'w', encoding='utf-8') as f:
                for entry in data["items"]:
                    json.dump(entry, f)
                    f.write('\n')

        except Exception as e:
            print(e)

    else:
        print(f"Failed with status code: {response.status_code}")
        print(response.text)
