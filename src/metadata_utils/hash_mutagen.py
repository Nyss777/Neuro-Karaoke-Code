from pathlib import Path

import xxhash


def get_audio_hash(file_path: Path) -> str | None:
    try:

        file_size = file_path.stat().st_size
        if file_size < 3000:
            print(f"{file_path.name} is too small!")
            return None

        with open(file_path, 'rb') as f:
            file_data = f.read()

            footer_size = 0
            f.seek(-128, 2) # Seek 128 bytes from the end (2)
            if f.read(3) == b'TAG':
                footer_size = 128
            

            if (file_size - footer_size - 1_000_000) > 987: # check to prevent negative indexes
                end_index = file_size - footer_size - 1_000_000 ### about a Mb offset for the audio

            else:
                end_index = int((file_size - footer_size)/2)

            start_index = end_index - 987 ### reads a 987 bytes for the hash

            raw_audio = file_data[start_index:end_index]

        # 4. Hash the raw audio
        return xxhash.xxh64(raw_audio).hexdigest()

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None
