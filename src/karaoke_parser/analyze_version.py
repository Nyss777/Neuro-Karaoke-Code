import json
import math
from pathlib import Path
from typing import Any, Callable, cast

from metadata_utils.CF_Program import Song, get_all_mp3_as_obj
from thefuzz import fuzz, process

with open(Path(__file__).parent.parent.parent / "config.json") as f:
    CONFIGS = json.load(f)

ARCHIVE_PATH = Path(CONFIGS["ARCHIVE_PATH"])

def wilson_interval(p: float, z: float, n: int) -> tuple[float, float]:
    term_1 = p + z**2/(2*n)
    term_2 = z*math.sqrt( p*(1-p)/n + z**2 / (4*n**2))
    divisor = 1 + z**2/n

    L = (term_1 - term_2)/divisor
    U = (term_1 + term_2)/divisor

    return L, U

def sample_definition(song: Song, positive: bool)-> bool:    

    if song.Discnumber in ("1", "2", "", None, "0"):
        return False

    if positive:
        return (song.CoverArtist == "Neuro" and song.Version != "3") or ("Evil" in song.CoverArtist and song.Version != "1")
    else:
        return (song.CoverArtist == "Neuro" and song.Version == "3") or ("Evil" in song.CoverArtist and song.Version == "1")

def get_sample(songs: list[Song], positive: bool) -> list[Song]:
    sample: list[Song] = []
    for song in songs:
        if sample_definition(song, positive):
            sample.append(song)

    return sample

def test(
    songs: list[Song], 
    scorer: Callable[[Any, Any], int],
    positive: bool
    ) -> set[tuple[Song, tuple[Song, int, int] | None]]:
    
    return set([(test, match_best(test, scorer, 90, songs)) for test in get_sample(songs, positive)])

def artist_filter(
    query: Song,
    scorer: Callable[[Any, Any], int], 
    score_cutoff: int, 
    songs: list[tuple[Song, int]]
    ) -> list[tuple[tuple[Song, int], int]] :

    matches = process.extractBests( # type: ignore
        query.Artist,
        songs,
        processor=lambda s: s[0].Artist if isinstance(s, tuple) and isinstance(s[0], Song) else s, # type: ignore
        scorer=scorer,
        score_cutoff=score_cutoff
        )

    matches = cast(list[tuple[tuple[Song, int], int]], matches)
    if not matches:
        return []

    return matches

def match_song(
    query: Song,
    scorer: Callable[[Any, Any], int], 
    score_cutoff: int, 
    songs: list[Song]
    ) -> list[tuple[Song, int]] :
    
    # song != query -> S . !P = N
    # song.CoverArtist == query.CoverArtist -> reduces error domain
    # song.Date <= query.Date

    choices = (
        song for song in songs 
        if song != query
        and song.CoverArtist == query.CoverArtist 
        and song.Date < query.Date
        )

    matches = process.extractBests( # type: ignore
        query.Title,
        choices,
        processor=lambda s: s.Title if isinstance(s, Song) else s, # type: ignore
        scorer=scorer,
        score_cutoff=score_cutoff
        )

    matches = cast(list[tuple[Song, int]], matches)
    if not matches:
        return []

    return matches

def match_best(
    query: Song,
    scorer: Callable[[Any, Any], int], 
    score_cutoff: int, 
    songs: list[Song]
    ) -> tuple[Song, int, int] | None:

    matches: list[tuple[Song, int]] = match_song(query, scorer, score_cutoff, songs)

    if not matches:
        return

    filtered_matches = [(fm[0][0], fm[0][1], fm[1]) for fm in artist_filter(query, fuzz.partial_ratio, score_cutoff, matches)] # type: ignore

    if not filtered_matches:
        return        

    baseline = filtered_matches[0][1]
    base_version = float(filtered_matches[0][0].Version)
    index = 0
    for i, match in enumerate(filtered_matches):
        if (match[1] == baseline) and (nv := float(match[0].Version) > base_version):
            baseline = match[1]
            base_version = nv
            index = i
    
    return filtered_matches[index]

def basic_negative_test(
    songs: list[Song], 
    scorer: Callable[[Any, Any], int]
    )-> set[tuple[Song, tuple[Song, int, int] | None]]:

    results = test(songs, scorer, positive=False) # type: ignore
    l_results = len(results)

    c = 0

    matches: set[tuple[Song, tuple[Song, int, int] | None]] = set()

    for result in results:
        if result[1]:
            c+=1
            matches.add(result)
            print(result[0])
            print(result[1])

    CI = wilson_interval((l_results-c)/l_results, 1.96, l_results)
    print(f"For {l_results}: {c} matches")
    print(f"{(l_results-c)/l_results*100:.2f}% estimated accuracy")
    print(f"Confidence Interval: [{CI[0]*100:.2f}%, {CI[1]*100:.2f}%]")

    return matches

def basic_positive_test(
    songs: list[Song], 
    scorer: Callable[[Any, Any], int]
    )-> set[tuple[Song, tuple[Song, int, int] | None]]:

    results = test(songs, scorer, positive=True)
    l_results = len(results)

    c = 0

    matches: set[tuple[Song, tuple[Song, int, int] | None]] = set()

    for result in results:
        if not result[1]:
            c+=1
            matches.add(result)
            print(result[0])
            print(result[1])

    CI = wilson_interval((l_results-c)/l_results, 1.96, l_results)
    print(f"For {l_results}: {c} unmatched")
    print(f"{(l_results-c)/l_results*100:.2f}% estimated accuracy")
    print(f"Confidence Interval: [{CI[0]*100:.2f}%, {CI[1]*100:.2f}%]")

    return matches


if __name__ == "__main__":

    # S definition
    songs = [song for song in get_all_mp3_as_obj(ARCHIVE_PATH) if song.Discnumber not in ("1", "2")]

    scorers: list[Callable[[Any, Any], int]] = [
        fuzz.ratio, 
        fuzz.partial_ratio, 
        fuzz.token_sort_ratio, 
        fuzz.token_set_ratio, 
        fuzz.QRatio, 
        fuzz.UQRatio, 
        fuzz.UWRatio
        ]

    scorers_names = [
        "ratio", 
        "partial_ratio", 
        "token_sort_ratio", 
        "token_set_ratio", 
        "QRatio", 
        "UQRatio", 
        "UWRatio"
        ]

    basic_scorer = basic_negative_test(songs, fuzz.token_sort_ratio) # type: ignore

    for i, scorer in enumerate(scorers):
        print(scorers_names[i])
        matches = basic_negative_test(songs, scorer) # type: ignore
        # for m in matches.difference(basic_scorer):
        #     print(m[0], m[0].Title)
        #     print(m[1], f"{m[1][0] if m[1] else None}")
        print()

# positives test are pretty much useless, they always 100%
# Identify is mixed with Title

# best accuracy is fuzz.UQRatio but it is too rigid
# I think UWRatio will fly better