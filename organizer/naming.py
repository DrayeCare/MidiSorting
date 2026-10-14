"""Aturan penamaan file untuk MIDI Organizer."""
from __future__ import annotations

import re

SEP = " - "
MAX_SONGS_PER_CATEGORY = 99

# Pola awalan nomor lama: 1-4 digit di awal, lalu pemisah yang dikenali.
# Pemisah: " - ", "-", "–", "—", ")", "]", "_", atau ". " (titik + spasi).
# Angka tanpa pemisah (mis. "7 Rings", "99 Luftballons") dianggap bagian judul.
_OLD_PREFIX_RE = re.compile(
    r"^\s*(?P<num>\d{1,4})(?:\s*[-–—)\]]\s*|_+\s*|\.\s+)(?P<rest>\S.*)$"
)


def strip_old_prefix(stem: str) -> tuple[str, str | None]:
    """Pisahkan (judul, nomor_lama) dari stem nama file.

    Mengembalikan nomor_lama=None jika awal nama tidak cocok dengan pola
    yang didukung; judul kemudian dibiarkan utuh (aman untuk judul seperti
    "3.14 - Pi Song" atau "7 Rings").
    """
    m = _OLD_PREFIX_RE.match(stem)
    if not m:
        return stem.strip(), None
    return m.group("rest").strip(), m.group("num")


def order_number(category_code: int, order: int) -> str:
    """Kode 1-9 -> tiga digit (mis. 101); kode >= 10 -> lebih panjang (mis. 1001)."""
    return f"{category_code}{order:02d}"


def build_name(category_code: int, order: int, title: str, ext: str) -> str:
    return f"{order_number(category_code, order)}{SEP}{title}{ext}"


def sanitize_title(title: str) -> str:
    """Bersihkan karakter yang tidak sah untuk nama file."""
    t = re.sub(r"\s+", " ", title).strip()
    t = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", t)
    t = t.rstrip(" .-")
    return t or "Tanpa Judul"