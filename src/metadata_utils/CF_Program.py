import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import TypedDict

from mutagen.id3 import (
    APIC,
    COMM,
    ID3,
    TALB,
    TDRC,
    TIT2,
    TPE1,
    TPE2,
    TPOS,
    TRCK,
    ID3NoHeaderError,
)
from tinytag import TinyTag

from .data_verification import validate_payload

logger = logging.getLogger(__name__)


class Song:

    filename: str = ''
    date: str = ''

    title: str = ''
    artist: str = ''
    cover_artist: str = ''
    version: str = ''
    disc_number: str = ''
    track: str = ''
    comment: str = ''
    special: str = ''
    xxhash: str = ''

    TIT2: str = '' # Title Tag
    TPE1: str = '' # Artist Tag
    TALB: str = '' # Album Tag
    COMM_ENG: str = ''  
    TRCK: str = ''

    image_type: str|None = None
    image_data: bytes|None = None

    def __init__(self, path: Path | str):
        self.path = Path(path)

        if self.path.suffix != ".mp3":
            raise ValueError("Incompatible format, only compatible with mp3s!")

        self.load()

    @property
    def ARG_MAP(self) -> dict[str, str]:
        return {
                "Date": "date",
                "Title": "title",
                "Artist": "artist",
                "CoverArtist": "cover_artist",
                "Version": "version",
                "Discnumber": "disc_number",
                "Track": "track",
                "xxHash": "xxhash",
               }
        
    @property
    def song_data(self) -> dict[str, str]:
        return {
                "Date": self.date,
                "Title": self.title,
                "Artist": self.artist,
                "CoverArtist": self.cover_artist,
                "Version": self.version,
                "Discnumber": self.disc_number,
                "Track": self.track,
                "Comment": self.comment,
                "xxHash": self.xxhash,
               }

    def load(self) -> None:
        data = self._get_song_data()
        self._load_dict(data)

    def save(self):
        self.process_new_tags
        self.set_tags
        self.engrave_payload

    def load_hjson(self, hjson_data: dict[str, (str | int | float)]) -> None:

        payload_kwargs = {
        self.ARG_MAP[field]: str(hjson_data.get(field)) for field in self.ARG_MAP
        }

        validate_payload(payload_kwargs)
        
        self._load_dict(payload_kwargs)

    def _load_dict(self, d: dict[str, str]):

        for dict_key, attr_name in self.ARG_MAP.items():
            if dict_key in d:
                setattr(self, attr_name, d[dict_key])
            else:            
                logger.warning(f"Missing key: {dict_key} - {self.filename}")

    def _get_song_data(self) -> dict[str, str]:

        """Quicker way to get a data dictionary, may not be as robust"""

        payload = self._get_raw_json()
        # "fields" assumes that the keys are constant, true for now but may change in the future.
        result = {field: self._get_raw_element(payload, field) for field in self.ARG_MAP}
        return result

    def _get_raw_json(self) -> str:

        """Return raw JSON string or an empty string."""

        path = Path(self.path)

        tags = TinyTag.get(path, tags=True, image=False)

        texts = tags.other.get("comment") or []
        if tags.comment:
            texts.append(tags.comment)

        if not texts:
            print("No comments found")
            return ""
        
        for text in texts:
            if text.startswith('{"Date":'):
                return text

        return ""

    def _get_raw_element(self, json: str, key: str) -> str:

        pattern = f"\"{key}\":\"(.*?)\""

        match = re.search(pattern, json)

        if match is None:
            return ""
        else:
            return match.group(1)

    def build_payload(self) -> str:
        
        # Validate all required fields
        for field_name, field_value in self.song_data.items():
            if not field_value:
                raise Exception(f"No {field_name.lower()} for {self.filename}!")
        
        # Build the payload dictionary
        payload = self.song_data.copy()
        payload["Comment"] = self.comment if self.comment else "None"
        payload["Special"] = self.special
        
        return json.dumps(payload)

    def engrave_payload(self) -> None:
        try:
            tags = ID3(self.path)
        except ID3NoHeaderError:
            tags = ID3()

        tags.add(COMM(encoding=3, lang='ved', desc='', text=[self.build_payload]))
        
        tags.save(self.path)

    def process_new_tags(self) -> None :

        try:

            self.TIT2 = self._substitution(pattern_defaults["TIT2"])

            if "&" in self.cover_artist:
                temp_filename = self._substitution(pattern_defaults["filename"][1])
                self.TPE1 = self._substitution(pattern_defaults["TPE1"][1])
            else:
                self.TPE1 = self._substitution(pattern_defaults["TPE1"][0])
                temp_filename = self._substitution(pattern_defaults["filename"][0])

            self.date = self._substitution(pattern_defaults["date"])
            self.TALB = self._substitution(pattern_defaults["TALB"])
            self.TRCK = self._substitution(pattern_defaults["TRCK"])

            if not self.comment:
                self.comment = "None"

            if self.comment != "None":
                self.COMM_ENG = self._substitution(pattern_defaults["COMM_ENG"][0])
            else:
                self.COMM_ENG = self._substitution(pattern_defaults["COMM_ENG"][1])  

            new_filename = sanitize_filename(temp_filename)
            new_filename += '.mp3'

            self.filename = new_filename

        except KeyError as e:
            print("Invalid Key:", e)

    def _substitution(self, new_pattern: str) -> str: 
        new_value = new_pattern
        for r_key, r_field in REPLACEMENT_MAP.items():
            new_value = new_value.replace(r_key, self.song_data[r_field])

        for s_key in secondary_map:
            new_value = new_value.replace(s_key, secondary_map[s_key](self.song_data))
        return new_value

    def set_tags(self) -> None:

        try:
            tags = ID3(self.path)
        except ID3NoHeaderError:
            # If no tags exist, create a blank ID3 object
            tags = ID3()
    
        tags.delall("TXXX")
        tags.add(TPE1(encoding=3, text=[self.TPE1]))
        tags.add(TALB(encoding=3, text=[self.TALB]))
        tags.add(TIT2(encoding=3, text=[self.TIT2]))
        tags.add(TRCK(encoding=3, text=[self.TRCK]))
        tags.add(TPE2(encoding=3, text=["QueenPb + vedal987"]))
        tags.add(TDRC(encoding=3, text=[self.COMM_ENG[:4]]))
        tags.add(TPOS(encoding=3, text=[self.TALB.replace("Disc ", "")]))

        NEW_COMM_ENG_FRAME = COMM(encoding=2,lang='eng', desc='',text=[self.COMM_ENG])
        tags.add(NEW_COMM_ENG_FRAME)
        NEW_COMM_V1_ENG_FRAME = COMM(encoding=2,lang='eng', desc='ID3v1 Comment',text=[self.COMM_ENG])
        tags.add(NEW_COMM_V1_ENG_FRAME)
        
        if self.image_data and self.image_type and (self.image_type.lower() in ("jpeg", "png")):

            tags.delall('APIC') 
                
            tags.add(
                APIC(
                    encoding=3,       
                    mime=f'image/{self.image_type.lower()}', 
                    type=3, 
                    desc='Cover (Front)', 
                    data=self.image_data
                )
            )
            logger.debug("Image added to APIC frame")

        tags.save(self.path)

    # def get_tag_value(tags: ID3, tag: str) -> (str | None) :
    #     frame = cast(Frame | None, tags.get(tag))

    #     if not isinstance(frame, Frame):
    #         return None
            
    #     return getattr(frame, 'text', None)

    # def get_content_from_tags(all_tags: ID3, tag: str) -> str:
    #     content_value = get_tag_value(all_tags, tag)
    #     if content_value is not None:
    #         content_text = str(content_value[0])
    #         return content_text
                
    #     return ""

REPLACEMENT_MAP = { "%t":"Title",
                    "%a":"Artist",
                    "%D":"Date",
                    "%c":"CoverArtist",
                    "%v":"Version",
                    "%A":"Discnumber",
                    "%T_n":"Track",
                    "%C":"Comment"
                    }

def get_track_number(song_data: dict[str, str]) -> str:

    """Extract track number from track info or filename, or use sequential numbering"""

    # Try to extract from track info (like "12/279")
    track_info = song_data["Track"]
    if track_info and '/' in track_info:
        track_num = track_info.split('/')[0]
        return track_num.zfill(3)  # 3-digit padding
    return track_info.zfill(3)

secondary_map = { "%N": get_track_number}

class Patterns(TypedDict):
    filename: tuple[str, str]
    TIT2: str
    TPE1: tuple[str, str]
    date: str
    TALB: str
    COMM_ENG: tuple[str, str] | str
    TRCK: str

pattern_defaults: Patterns = {
    "filename": ("%N. %a - %t (%c.v%v)", "%N. %a - %t (Duet.v%v) (%c)"),
    "TIT2": "%t",
    "TPE1": ("%c - %a", "Duet (%c) - %a"),
    "date": "%D",
    "TALB": "Disc %A",
    "COMM_ENG": ("%D //%C", "%D"),
    "TRCK": "%T_n"
}

def get_all_mp3_as_obj(directory: str) -> list[Song]: 
    """
    Returns as Song objects all mp3 files from a directory and it's sub-directories.
    """
    p = Path(directory)
    return [(Song(f)) for f in p.rglob('*.mp3') if f.is_file()]



def sanitize_filename(filename: str) -> str:
    FORBIDDEN_CHARS = {
        '\\': ' backslash ',
        '/': ' slash ',
        ':': ' ', 
        '*': '_', 
        '?': ' ',
        '"': "'",
        '<': '[',
        '>': ']',
        '|': '_'
    }

    for char in FORBIDDEN_CHARS:
        filename = filename.replace(char, FORBIDDEN_CHARS[char])

    while("  " in filename):
        filename = filename.replace("  ", " ")

    ## some kanji were getting divided into two symbols: ヴ -> ウ  ゙
    filename = unicodedata.normalize('NFC', filename)

    return filename

