import json
import logging
import re
import unicodedata
from pathlib import Path

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

# from .data_verification import validate_payload

logger = logging.getLogger(__name__)

class Song:
    
    Date: str = ''
    Title: str = ''
    Artist: str = ''
    CoverArtist: str = ''
    Version: str = ''
    Discnumber: str = ''
    Track: str = ''
    Comment: str = ''
    Special: str = ''
    xxHash: str = ''

    @property
    def filename(self) -> str:
    
        if '&' not in self.CoverArtist:
            filename = f"{self.TRCK}. {self.Artist} - {self.Title} ({self.CoverArtist}.v{self.Version})"

        else:
            filename = f"{self.TRCK}. {self.Artist} - {self.Title} (Duet.v{self.Version}) ({self.CoverArtist})"
            
        filename = sanitize_filename(filename)
        filename += '.mp3'

        return filename

    @property
    def TIT2(self) -> str:
        return self.Title

    @property
    def TPE1(self) -> str:
        if '&' not in self.CoverArtist:
            return  f"{self.CoverArtist} - {self.Artist}"
        else:
            return f"Duet ({self.CoverArtist}) - {self.Artist}"

    @property
    def TALB(self) -> str:
        return f"Disc {self.Discnumber}"

    @property
    def TDRC(self) -> str:
        return self.COMM_ENG[:4]

    @property
    def COMM_ENG(self) -> str:
        if not self.Comment:
            self.Comment = "None"

        if self.Comment != "None":
            return f"{self.Date} //{self.Comment}"
        else:
            return self.Date 

    @property
    def TRCK(self) -> str:

        """Track number with 3-digit padding"""

        # Try to extract from Track info (like "12/279")
        track_info = self.Track
        if track_info and '/' in track_info:
            track_num = track_info.split('/')[0]
            return track_num.zfill(3)  # 3-digit padding
        return track_info.zfill(3)

    image_type: str|None = None
    image_data: bytes|None = None

    FIELDS = (
            "Date", 
            "Title", 
            "Artist", 
            "CoverArtist", 
            "Version", 
            "Discnumber", 
            "Track", 
            "Special",
            "xxHash"
            )

    def __init__(self, path: Path | str):
        self.path = Path(path)

        if self.path.suffix != ".mp3":
            raise ValueError("Incompatible format, only compatible with mp3s!")

        self.load()

    def load(self) -> None:
        data = self._get_song_data()
        self._load_dict(data)

    def save(self) -> None:
        self.set_tags()

    def load_hjson(self, hjson_data: dict[str, (str | int | float)]) -> None:

        data = {
        field: str(hjson_data.get(field)) for field in self.FIELDS
        }

        if data["Special"] == "None":
            data["Special"] = "0"

        # validate_payload(payload_kwargs)
        
        self._load_dict(data)

    def _load_dict(self, d: dict[str, str]):

        for field in self.FIELDS:
            if field in d:
                setattr(self, field, d[field])
            else:            
                logger.warning(f"Missing key: {field} - {self.filename}")

    def _get_song_data(self) -> dict[str, str]:

        """Quicker way to get a data dictionary, may not be as robust"""

        payload = self._get_raw_json()
        # "fields" assumes that the keys are constant, true for now but may change in the future.
        result = {field: self._get_raw_element(payload, field) for field in self.FIELDS}
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
        
        payload = {}

        for field in self.FIELDS:
            field_value = getattr(self, field)
            payload[field] = field_value
        
        payload["Comment"] = self.Comment if self.Comment else "None"
        
        return json.dumps(payload)
    
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
        tags.add(TDRC(encoding=3, text=[self.TDRC]))
        tags.add(TPOS(encoding=3, text=[self.TALB.replace("Disc ", "")]))

        tags.add(COMM(encoding=3, lang='ved', desc='', text=[self.build_payload()]))
        tags.add(COMM(encoding=2,lang='eng', desc='',text=[self.COMM_ENG]))
        tags.add(COMM(encoding=2,lang='eng', desc='ID3v1 Comment',text=[self.COMM_ENG]))
        
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

