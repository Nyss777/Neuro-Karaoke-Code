import pytest
from parse import parse_coverartist, parse_date, sanitize_artist


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("**Neuro Mini-Karaoke Stream Setlist (28/07/2026)**",           "Neuro"),
        ("**Neuro Karaoke Stream Setlist (19/08/2026)**",                "Neuro"),
        ("**Neuro Mini-Karaoke Stream setlist (08/09/2026)**",           "Neuro"),
        ("**Neuro Karaoke Stream Setlist (16/09/2026)**",                "Neuro"),
        ("**Evil Neuro Karaoke Stream setlist (05/08/2026)**",           "Evil"),
        ("**Evil Neuro Mini-Karaoke Stream Setlist (13/08/2026)**",      "Evil"),
        ("**Evil Neuro Karaoke Stream setlist (02/09/2026)**",           "Evil"),
        ("** Evil Neuro Mini-Karaoke Stream setlist (25/09/2026)**",     "Evil"),
        ("**Evil Neuro Mini-Karaoke Stream setlist (22/10/2026)**",      "Evil"),
        ("**Evil Neuro Halloween Karaoke Stream setlist (29/10/2026)**", "Evil"),
        ("**Twin Karaoke Stream Setlist (30/09/2026)**",                 "Twin"),
        ("Trio Karaoke Stream setlist (26/09/2026)",                      None),
    ],
)
def test_coverartist(header: str, expected: str):
    assert parse_coverartist(header) == expected


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("**Neuro Mini-Karaoke Stream Setlist (28/07/2026)**",           "2026-07-28"),
        ("**Neuro Karaoke Stream Setlist (19/08/2026)**",                "2026-08-19"),
        ("**Neuro Mini-Karaoke Stream setlist (08/09/2026)**",           "2026-09-08"),
        ("**Neuro Karaoke Stream Setlist (16/09/2026)**",                "2026-09-16"),
        ("**Evil Neuro Karaoke Stream setlist (05/08/2026)**",           "2026-08-05"),
        ("**Evil Neuro Mini-Karaoke Stream Setlist (13/08/2026)**",      "2026-08-13"),
        ("**Evil Neuro Karaoke Stream setlist (02/09/2026)**",           "2026-09-02"),
        ("** Evil Neuro Mini-Karaoke Stream setlist (25/09/2026)**",     "2026-09-25"),
        ("**Evil Neuro Mini-Karaoke Stream setlist (22/10/2026)**",      "2026-10-22"),
        ("**Evil Neuro Halloween Karaoke Stream setlist (29/10/2026)**", "2026-10-29"),
        ("**Twin Karaoke Stream Setlist (30/09/2026)**",                 "2026-09-30"),
        ("Trio Karaoke Stream setlist (26/09/2026)",                     "2026-09-26"),
    ],
)
def test_parse_date(header: str, expected: str):
    assert parse_date(header) == expected

@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("Earth, Wind & Fire",        "Earth, Wind & Fire"),
        ("Simon & Garfunkel",         "Simon & Garfunkel"),
        ("Levia & bitbreaker",        "Levia, bitbreaker"),
        ("Giga & TeddyLoid",          "Giga, TeddyLoid"),
        ("Muse & Ellie Goulding",     "Muse, Ellie Goulding"),
        ("Halestorm & I Prevail",     "Halestorm, I Prevail"),
        ("Porter Robinson & Madeon",  "Porter Robinson, Madeon"),
        ("Bad Omens, HEALTH & SWARM", "Bad Omens, HEALTH, SWARM"),
    ],
)
def test_sanitize_artist(header: str, expected: str):
    assert sanitize_artist(header) == expected










