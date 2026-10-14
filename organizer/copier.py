"""Penyalinan file di latar belakang + pembatalan hasil terakhir."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, Signal


@dataclass
class CopyTask:
    file_id: str
    source: Path
    target: Path
    target_name: str
    category_name: str
    order: int


class CopyWorker(QThread):
    progress = Signal(int, int, str)   # selesai, total, nama
    item_done = Signal(str, str, str)  # file_id, status, pesan
    all_done = Signal(list)            # daftar aksi (laporan/undo)

    def __init__(self, tasks, mode: str, backup_root, parent=None):
        super().__init__(parent)
        self._tasks = list(tasks)
        self._mode = mode  # "skip" | "overwrite" | "rename"
        self._backup_root = Path(backup_root)
        self._taken: set[str] = set()

    def run(self):
        actions: list[dict] = []
        total = len(self._tasks)
        for i, t in enumerate(self._tasks, start=1):
            self.progress.emit(i - 1, total, t.target_name)
            final = t.target
            try:
                status, message, backup, final = self._process(t)
            except Exception as exc:
                status, message, backup = "failed", f"Gagal: {exc}", None
            actions.append({
                "file_id": t.file_id,
                "source": str(t.source),
                "target": str(final),
                "final_name": final.name,
                "planned_name": t.target_name,
                "category": t.category_name,
                "order": t.order,
                "status": status,
                "message": message,
                "backup": backup,
            })
            self.item_done.emit(t.file_id, status, message)
        self.all_done.emit(actions)

    def _process(self, t: CopyTask):
        if not t.source.exists():
            return "failed", "File sumber tidak ditemukan", None, t.target

        # Jika sumber == tujuan (nama sudah benar), tidak perlu menyalin.
        if t.target.exists() and t.source.samefile(t.target):
            self._taken.add(t.target.name.lower())
            return "unchanged", "Nama sudah sesuai", None, t.target

        target = t.target
        backup = None
        status = "copied"
        occupied = target.exists() or target.name.lower() in self._taken
        if occupied:
            if self._mode == "skip":
                return "skipped", "Dilewati: nama tujuan sudah ada", None, target
            if self._mode == "overwrite":
                backup = self._backup_existing(target)
                status = "overwritten"
            else:  # rename
                target = self._alternate(target)
                status = "renamed"
        self._taken.add(target.name.lower())
        shutil.copy2(t.source, target)
        return status, f"Disalin sebagai {target.name}", backup, target

    def _backup_existing(self, target: Path) -> str:
        self._backup_root.mkdir(parents=True, exist_ok=True)
        dst = self._backup_root / target.name
        i = 2
        while dst.exists():
            dst = self._backup_root / f"{target.stem} ({i}){target.suffix}"
            i += 1
        shutil.move(str(target), str(dst))
        return str(dst)

    def _alternate(self, target: Path) -> Path:
        cand = target
        i = 2
        while cand.exists() or cand.name.lower() in self._taken:
            cand = target.with_name(f"{target.stem} ({i}){target.suffix}")
            i += 1
        return cand


def perform_undo(op: dict) -> list[str]:
    """Batalkan hasil terakhir: hapus salinan, pulihkan yang dicadangkan."""
    lines: list[str] = []
    for act in reversed(op.get("actions", [])):
        status = act.get("status")
        target = Path(act["target"]) if act.get("target") else None
        if target is None:
            continue
        if status in ("copied", "renamed"):
            if target.exists():
                try:
                    target.unlink()
                    lines.append(f"Dihapus: {target.name}")
                except OSError as exc:
                    lines.append(f"Gagal menghapus {target.name}: {exc}")
        elif status == "overwritten":
            backup = act.get("backup")
            if backup and Path(backup).exists():
                try:
                    if target.exists():
                        target.unlink()
                    shutil.move(backup, str(target))
                    lines.append(f"Dipulihkan: {target.name}")
                except (OSError, shutil.Error) as exc:
                    lines.append(f"Gagal memulihkan {target.name}: {exc}")
            else:
                lines.append(f"Cadangan hilang, {target.name} dibiarkan")
        # skipped / unchanged / failed -> tidak ada yang perlu dibatalkan
    root = op.get("backup_root")
    if root:
        try:
            Path(root).rmdir()  # hanya berhasil jika kosong
        except OSError:
            pass
    return lines