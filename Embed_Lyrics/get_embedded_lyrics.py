from pathlib import Path

from tinytag import TinyTag


def get_embedded_lyrics(path: Path | str) -> set[str]:

    path = Path(path)

    tags = TinyTag.get(path, tags=True, image=False)

    lyrics = tags.other.get("lyrics") or []

    return set(lyrics)

# Example usage

if __name__ == "__main__":

    print(get_embedded_lyrics(r"C:\Users\Nyss\Downloads\test_lyrics\Relay Outer Combined.mp3"))