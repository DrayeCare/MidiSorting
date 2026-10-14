"""Model data dan penyimpanan konfigurasi JSON."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path.home() / ".midi_organizer"
CONFIG_PATH = CONFIG_DIR / "config.json"
BACKUP_DIR = CONFIG_DIR / "backups"

DEFAULT_CATEGORY_NAMES = [
    "Mondstadt", "Liyue", "Inazuma", "Sumeru",
    "Fontaine", "Natlan", "Nod-Krai", "Snezhnaya",
]


def new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class SongFile:
    id: str
    path: str
    title: str
    old_prefix: str | None = None


@dataclass
class Category:
    id: str
    code: int
    name: str
    song_ids: list[str] = field(default_factory=list)


@dataclass
class AppState:
    next_category_code: int = 1
    destination: str = ""
    categories: list[Category] = field(default_factory=list)
    files: dict[str, SongFile] = field(default_factory=dict)
    inbox: list[str] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)  # catatan pemrosesan

    def category_by_id(self, cid: str) -> Category | None:
        return next((c for c in self.categories if c.id == cid), None)

    @classmethod
    def make_default(cls) -> "AppState":
        st = cls()
        for i, name in enumerate(DEFAULT_CATEGORY_NAMES, start=1):
            st.categories.append(Category(new_id(), i, name))
        st.next_category_code = len(DEFAULT_CATEGORY_NAMES) + 1
        return st


def load_state() -> AppState:
    if not CONFIG_PATH.exists():
        st = AppState.make_default()
        save_state(st)
        return st
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return AppState.make_default()

    if not isinstance(data, dict) or "categories" not in data:
        return AppState.make_default()

    st = AppState()
    st.next_category_code = int(data.get("next_category_code", 1))
    st.destination = str(data.get("destination", ""))
    st.files = {
        fid: SongFile(fid, d.get("path", ""), d.get("title", ""), d.get("old_prefix"))
        for fid, d in (data.get("files") or {}).items()
        if isinstance(d, dict)
    }
    valid = set(st.files)
    st.categories = [
        Category(
            c.get("id", new_id()),
            int(c.get("code", 0)),
            str(c.get("name", "Kategori")),
            [i for i in (c.get("song_ids") or []) if i in valid],
        )
        for c in (data.get("categories") or [])
    ]
    st.inbox = [i for i in (data.get("inbox") or []) if i in valid]
    st.history = [h for h in (data.get("history") or []) if isinstance(h, dict)]
    return st


def save_state(state: AppState) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "version": 1,
        "next_category_code": state.next_category_code,
        "destination": state.destination,
        "categories": [
            {"id": c.id, "code": c.code, "name": c.name, "song_ids": list(c.song_ids)}
            for c in state.categories
        ],
        "files": {
            f.id: {"path": f.path, "title": f.title, "old_prefix": f.old_prefix}
            for f in state.files.values()
        },
        "inbox": list(state.inbox),
        "history": state.history[-20:],
    }
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_PATH)