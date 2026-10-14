import pytest

from organizer.naming import build_name, order_number, sanitize_title, strip_old_prefix


@pytest.mark.parametrize("stem,expected", [
    ("003 - Rex Incognito", ("Rex Incognito", "003")),
    ("01 - Lover's Oath", ("Lover's Oath", "01")),
    ("201 - Rex Incognito", ("Rex Incognito", "201")),
    ("101 - Dawn Winery", ("Dawn Winery", "101")),
    ("05. Lover's Oath", ("Lover's Oath", "05")),
    ("01_Lover's Oath", ("Lover's Oath", "01")),
    ("7) overworld", ("overworld", "7")),
    ("12 -  Spaced", ("Spaced", "12")),
    # Harus TIDAK dianggap nomor lama (bagian dari judul):
    ("7 Rings", ("7 Rings", None)),
    ("99 Luftballons", ("99 Luftballons", None)),
    ("3.14 - Pi Song", ("3.14 - Pi Song", None)),
    ("12345 - X", ("12345 - X", None)),
    ("- 5 - Dash", ("- 5 - Dash", None)),
])
def test_strip_old_prefix(stem, expected):
    assert strip_old_prefix(stem) == expected


def test_order_number():
    assert order_number(1, 1) == "101"
    assert order_number(1, 23) == "123"
    assert order_number(9, 99) == "999"
    assert order_number(10, 1) == "1001"   # kode >= 10 -> digit bertambah


def test_build_name():
    assert build_name(2, 1, "Rex Incognito", ".mid") == "201 - Rex Incognito.mid"


def test_sanitize_title():
    assert sanitize_title('A<B:C"') == "A-B-C"
    assert sanitize_title("AC/DC Live") == "AC-DC Live"
    assert sanitize_title("   ") == "Tanpa Judul"