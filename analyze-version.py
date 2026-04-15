import math
from pathlib import Path
from typing import Any, Callable, cast

from metadata_utils.CF_Program import Song, get_all_mp3_as_obj
from thefuzz import fuzz, process

# given test and songs

# for song in songs
# match title and artist
# make match list

# find latest in match list
# return positive

FULL_ALBUM_PATH = Path(r"C:\Users\Nyss\Downloads\Neuro Karaoke Archive")

# Scorer and Cutoffs
# ratio	General-purpose matching	Simple character-level similarity (0-100). Good baseline.
# partial_ratio	Substring matching	Finds best matching substring. Great if one string is much shorter.
# token_sort_ratio	Word order differences	Sorts tokens alphabetically, then compares. Handles reordered words.
# token_set_ratio	Duplicated/missing words	Handles both reordered words AND words that appear in one string but not the other.
# QRatio	Quick matching	Fast approximation of ratio. Use when speed matters more than precision.
# UQRatio	Quick Unicode matching	Unicode-aware version of QRatio.
# UWRatio

def wilson_interval(p: float, z: float, n: int) -> tuple[float, float]:
    term_1 = p + z**2/(2*n)
    term_2 = z*math.sqrt( p*(1-p)/n + z**2 / (4*n**2))
    divisor = 1 + z**2/n

    # L = (p̂ + z²/(2n) - z√[p̂(1-p̂)/n + z²/(4n²)]) / (1 + z²/n)
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

def get_sample(positive: bool) -> list[Song]:
    songs: list[Song] = []
    for song in get_all_mp3_as_obj(FULL_ALBUM_PATH / "DISC 8 - Third Anniversary (2025-12-19 - Present)" ):
        if sample_definition(song, positive):
            songs.append(song)

    return songs

def test(
    songs: list[Song], 
    scorer: Callable[[Any, Any], int],
    positive: bool
    ) -> set[tuple[Song, tuple[Song, int] | None]]:
    
    return set([(test, match_best(test, scorer, 90, songs)) for test in get_sample(positive)])

def match_song(
    query: Song,
    scorer: Callable[[Any, Any], int], 
    score_cutoff: int, 
    songs: list[Song]
    ) -> list[tuple[Song, int]] | None:
    
    choices = (song for song in songs if song.Discnumber != "8" and song.CoverArtist == query.CoverArtist)

    matches = process.extractBests( # type: ignore
        query.Title,
        choices,
        processor=lambda s: s.Title if isinstance(s, Song) else s, # type: ignore
        scorer=scorer,
        score_cutoff=score_cutoff
        )

    matches = cast(list[tuple[Song, int]], matches)
    if not matches:
        return

    return matches

def match_best(
    query: Song,
    scorer: Callable[[Any, Any], int], 
    score_cutoff: int, 
    songs: list[Song]
    ) -> tuple[Song, int] | None:

    matches: list[tuple[Song, int]] | None = match_song(query, scorer, score_cutoff, songs)

    if not matches:
        return

    baseline = matches[0][1]
    base_version = float(matches[0][0].Version)
    index = 0
    for i, match in enumerate(matches):
        if (match[1] == baseline) and (nv := float(match[0].Version) > base_version):
            baseline = match[1]
            base_version = nv
            index = i
    
    return matches[index]

def basic_negative_test(
    songs: list[Song], 
    scorer: Callable[[Any, Any], int]
    )-> set[tuple[Song, tuple[Song, int] | None]]:
    results = test(songs, scorer, positive=False) # type: ignore
    l_results = len(results)

    c = 0

    matches: set[tuple[Song, tuple[Song, int] | None]] = set()

    for result in results:
        if result[1]:
            c+=1
            matches.add(result)
            # print(result[0])
            # print(result[1])

    CI = wilson_interval((l_results-c)/l_results, 1.96, l_results)
    print(f"For {l_results}: {c} matches")
    print(f"{(l_results-c)/l_results*100:.2f}% estimated accurasy")
    print(f"Confidence Interval: [{CI[0]*100:.2f}%, {CI[1]*100:.2f}%]")

    return matches

if __name__ == "__main__":

    songs = [song for song in get_all_mp3_as_obj(FULL_ALBUM_PATH)]

    scorers = [
        #fuzz.ratio, 
        fuzz.partial_ratio, fuzz.token_sort_ratio, fuzz.token_set_ratio, fuzz.QRatio, fuzz.UQRatio, fuzz.UWRatio]

    scorers_names = [
        #fuzz.ratio, 
        "partial_ratio", "token_sort_ratio", "token_set_ratio", "QRatio", "UQRatio", "UWRatio"]


    # best so far for negatives = token_sort_ratio, fuzz.QRatio, fuzz.UQRatio

    basic_scorer = basic_negative_test(songs, fuzz.ratio) # too rigid

    for i, scorer in enumerate(scorers):
        print(scorers_names[i])
        matches = basic_negative_test(songs, scorer) # type: ignore
        for m in matches.difference(basic_scorer):
            pass
            # print(m[0])
            # print(m[1])
        print()