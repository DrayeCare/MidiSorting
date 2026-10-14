"""Jendela utama MIDI Organizer."""
from __future__ import annotations

import os
from collections import Counter
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFileDialog, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QSplitter, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from .. import naming, storage
from ..copier import CopyTask, CopyWorker, perform_undo
from .dialogs import ConflictDialog, ReportDialog
from .widgets import CategoryCard, InboxPanel

WARN_COLOR = QColor("#c0392b")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MIDI Organizer")
        self.resize(1280, 760)
        self.state = storage.load_state()
        self.cards: dict[str, CategoryCard] = {}
        self.worker: CopyWorker | None = None

        self._build_ui()
        self._refresh_all()
        self.log.appendPlainText(f"Konfigurasi disimpan di: {storage.CONFIG_PATH}")

    # ================= UI =================
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        top = QHBoxLayout()
        top.addWidget(QLabel("<b style='font-size:14pt'>MIDI Organizer</b>"))
        top.addStretch(1)
        self.btn_undo = QPushButton("↩ Batalkan Hasil Terakhir")
        btn_add_cat = QPushButton("＋ Tambah Kategori")
        top.addWidget(self.btn_undo)
        top.addWidget(btn_add_cat)
        root.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Kiri: File Masuk
        self.inbox = InboxPanel()
        self.inbox.setMinimumWidth(230)
        splitter.addWidget(self.inbox)

        # Tengah: kategori
        self.cat_scroll = QScrollArea()
        self.cat_scroll.setWidgetResizable(True)
        self.cat_host = QWidget()
        self.cat_lay = QVBoxLayout(self.cat_host)
        self.cat_lay.setContentsMargins(4, 4, 4, 4)
        self.cat_lay.setSpacing(8)
        self.cat_lay.addStretch(1)
        self.cat_scroll.setWidget(self.cat_host)
        splitter.addWidget(self.cat_scroll)

        # Kanan: preview + folder hasil + terapkan + log
        right = QWidget()
        rlay = QVBoxLayout(right)
        rlay.addWidget(QLabel("<b>Preview Nama File</b>"))
        self.preview_label = QLabel("")
        rlay.addWidget(self.preview_label)
        self.preview = QTableWidget(0, 5)
        self.preview.setHorizontalHeaderLabels(
            ["Kategori", "No", "Nama Sekarang", "Nama Hasil", "Status"]
        )
        self.preview.verticalHeader().setVisible(False)
        self.preview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.preview.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self.preview.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        rlay.addWidget(self.preview, 2)

        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("Folder hasil:"))
        self.dest_edit = QLineEdit()
        self.dest_edit.setReadOnly(True)
        self.dest_edit.setPlaceholderText("Belum dipilih")
        btn_dest = QPushButton("Pilih…")
        dest_row.addWidget(self.dest_edit, 1)
        dest_row.addWidget(btn_dest)
        rlay.addLayout(dest_row)

        apply_row = QHBoxLayout()
        self.apply_btn = QPushButton("✔ Terapkan — Salin ke Folder Hasil")
        self.apply_btn.setStyleSheet("font-weight:600;")
        self.progress_label = QLabel("")
        apply_row.addWidget(self.apply_btn, 1)
        apply_row.addWidget(self.progress_label)
        rlay.addLayout(apply_row)

        rlay.addWidget(QLabel("<b>Log</b>"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        rlay.addWidget(self.log, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 2)
        splitter.setSizes([250, 400, 620])
        root.addWidget(splitter, 1)

        # Koneksi
        self.inbox.filesDropped.connect(self.add_files)
        self.inbox.idsDropped.connect(lambda ids, row: self._move_ids(ids, "inbox", row))
        self.inbox.deletePressed.connect(self.remove_files)
        btn_add_cat.clicked.connect(self.add_category)
        self.btn_undo.clicked.connect(self.undo_last)
        btn_dest.clicked.connect(self.choose_destination)
        self.apply_btn.clicked.connect(self.apply)

    # ================= Pembaruan tampilan =================
    def _sync_cards(self):
        current = {c.id for c in self.state.categories}
        for cid in [cid for cid in self.cards if cid not in current]:
            card = self.cards.pop(cid)
            card.setParent(None)
            card.deleteLater()
        for cat in self.state.categories:
            card = self.cards.get(cat.id)
            if card is None:
                card = CategoryCard(cat.id, cat.code, cat.name)
                card.idsDropped.connect(self._on_ids_dropped)
                card.filesDropped.connect(lambda cid, paths: self.add_files(paths, cid))
                card.renameRequested.connect(self.rename_category)
                card.deleteRequested.connect(self.delete_category)
                card.deletePressed.connect(self._files_back_to_inbox)
                self.cards[cat.id] = card
                self.cat_lay.insertWidget(self.cat_lay.count() - 1, card)
            else:
                card.set_header(cat.name, cat.code)

    def _refresh_all(self):
        self._sync_cards()
        self._refresh_inbox()
        self._refresh_cards()
        self._refresh_preview()
        self.dest_edit.setText(self.state.destination)
        self.btn_undo.setEnabled(bool(self.state.history))

    def _refresh_inbox(self):
        rows = []
        for fid in self.state.inbox:
            f = self.state.files.get(fid)
            if not f:
                continue
            mark = "⚠ " if not Path(f.path).exists() else ""
            rows.append((fid, f"{mark}{Path(f.path).name}", f.path))
        self.inbox.set_files(rows)

    def _refresh_cards(self):
        for cat in self.state.categories:
            card = self.cards.get(cat.id)
            if not card:
                continue
            rows = []
            for i, fid in enumerate(cat.song_ids, start=1):
                f = self.state.files.get(fid)
                if not f:
                    continue
                mark = "⚠ " if not Path(f.path).exists() else ""
                tip = f.path + (f"\nNomor lama: {f.old_prefix}" if f.old_prefix else "")
                rows.append((fid, f"{mark}{i:02d} · {f.title}", tip))
            card.set_songs(rows)

    def _refresh_preview(self):
        rows = self._compute_rows()
        self.preview.setRowCount(len(rows))
        red = QBrush(WARN_COLOR)
        for i, r in enumerate(rows):
            if r["kind"] == "cat":
                status = "; ".join(r["warnings"]) or (
                    "Sudah sesuai" if r["already_ok"] else "Siap"
                )
                vals = [r["category"], r["number"], r["current_name"],
                        r["target_name"], status]
            else:
                vals = ["—", "—", r["current_name"], "—", "Belum dikategorikan"]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                if r["warnings"]:
                    it.setForeground(red)
                if c == 2 and r["old_prefix"]:
                    it.setToolTip(f"Nomor lama terdeteksi: {r['old_prefix']} — akan diganti")
                self.preview.setItem(i, c, it)
        n_cat = sum(1 for r in rows if r["kind"] == "cat")
        n_warn = sum(1 for r in rows if r["warnings"])
        self.preview_label.setText(
            f"{n_cat} file terkategori · {n_warn} peringatan · {len(rows) - n_cat} di File Masuk"
        )

    # ================= Logika inti =================
    def _compute_rows(self) -> list[dict]:
        rows: list[dict] = []
        name_counts: Counter = Counter()
        dest = Path(self.state.destination) if self.state.destination else None

        for cat in self.state.categories:
            for idx, fid in enumerate(cat.song_ids, start=1):
                f = self.state.files.get(fid)
                if f is None:
                    continue
                src = Path(f.path)
                number = naming.order_number(cat.code, idx)
                target_name = f"{number}{naming.SEP}{f.title}{src.suffix}"
                rows.append({
                    "file_id": fid, "kind": "cat", "category": cat.name,
                    "order": idx, "number": number, "source": src,
                    "current_name": src.name, "target_name": target_name,
                    "old_prefix": f.old_prefix, "already_ok": False,
                })
                name_counts[target_name.lower()] += 1

        for fid in self.state.inbox:
            f = self.state.files.get(fid)
            if f is None:
                continue
            src = Path(f.path)
            rows.append({
                "file_id": fid, "kind": "inbox", "category": "—",
                "order": None, "number": "—", "source": src,
                "current_name": src.name, "target_name": "—",
                "old_prefix": f.old_prefix, "already_ok": False,
            })

        for r in rows:
            warns: list[str] = []
            if not r["source"].exists():
                warns.append("File sumber tidak ditemukan")
            if r["kind"] == "cat":
                if r["order"] > naming.MAX_SONGS_PER_CATEGORY:
                    warns.append(f"Lewati batas {naming.MAX_SONGS_PER_CATEGORY} lagu per kategori")
                if name_counts[r["target_name"].lower()] > 1:
                    warns.append("Nama hasil duplikat")
                if dest is not None and r["source"].exists():
                    tgt = dest / r["target_name"]
                    if tgt.exists():
                        try:
                            same = r["source"].samefile(tgt)
                        except OSError:
                            same = False
                        if same:
                            r["already_ok"] = True
                        else:
                            warns.append("Nama sudah dipakai di folder hasil")
            r["warnings"] = warns
        return rows

    def add_files(self, paths: list, category_id: str | None = None):
        added, skipped = 0, 0
        known = {os.path.normcase(f.path) for f in self.state.files.values()}
        for p in paths:
            path = Path(p)
            if path.suffix.lower() not in (".mid", ".midi"):
                skipped += 1
                continue
            try:
                full = str(path.resolve())
            except OSError:
                full = str(path.absolute())
            key = os.path.normcase(full)
            if key in known:
                skipped += 1
                continue
            fid = storage.new_id()
            title, old = naming.strip_old_prefix(path.stem)
            self.state.files[fid] = storage.SongFile(
                id=fid, path=full, title=naming.sanitize_title(title), old_prefix=old
            )
            known.add(key)
            cat = self.state.category_by_id(category_id) if category_id else None
            if cat is not None:
                cat.song_ids.append(fid)
            else:
                self.state.inbox.append(fid)
            added += 1
        if added or skipped:
            if skipped:
                self.log.appendPlainText(
                    f"{skipped} item dilewati (bukan .mid/.midi atau sudah ada di daftar)."
                )
            self._refresh_all()
            self._save()

    def _container_list(self, key: str):
        if key == "inbox":
            return self.state.inbox
        cat = self.state.category_by_id(key)
        return cat.song_ids if cat else None

    def _container_of_file(self, fid: str):
        if fid in self.state.inbox:
            return self.state.inbox
        for c in self.state.categories:
            if fid in c.song_ids:
                return c.song_ids
        return None

    def _on_ids_dropped(self, target_key: str, ids: list, row: int):
        self._move_ids(ids, target_key, row)

    def _files_back_to_inbox(self, _cid: str, ids: list):
        self._move_ids(ids, "inbox", len(self.state.inbox))

    def _move_ids(self, ids: list, target_key: str, row: int):
        dst = self._container_list(target_key)
        if dst is None:
            return
        ids = [i for i in ids
               if i in self.state.files and self._container_of_file(i) is not None]
        if not ids:
            return
        src = self._container_of_file(ids[0])
        if src is dst:
            sel_rows = sorted(dst.index(i) for i in ids if i in dst)
            row -= sum(1 for r in sel_rows if r < row)
            for i in ids:
                if i in dst:
                    dst.remove(i)
            row = max(0, min(row, len(dst)))
            for off, i in enumerate(ids):
                dst.insert(row + off, i)
        else:
            for i in ids:
                s = self._container_of_file(i)
                if s is not None:
                    s.remove(i)
            row = max(0, min(row, len(dst)))
            for off, i in enumerate(ids):
                dst.insert(row + off, i)
        self._refresh_all()
        self._save()

    def remove_files(self, ids: list):
        ids = [i for i in ids if i in self.state.files]
        if not ids:
            return
        ret = QMessageBox.question(
            self, "Hapus dari Daftar",
            f"Hapus {len(ids)} file dari daftar aplikasi?\nFile di komputer tidak akan diubah.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        gone = set(ids)
        self.state.inbox = [i for i in self.state.inbox if i not in gone]
        for c in self.state.categories:
            c.song_ids = [i for i in c.song_ids if i not in gone]
        for i in ids:
            self.state.files.pop(i, None)
        self._refresh_all()
        self._save()

    # ================= Kategori =================
    def add_category(self):
        name, ok = QInputDialog.getText(self, "Kategori Baru", "Nama kategori:")
        if not ok or not name.strip():
            return
        cat = storage.Category(storage.new_id(), self.state.next_category_code, name.strip())
        self.state.next_category_code += 1  # kode tidak pernah dipakai ulang
        self.state.categories.append(cat)
        self._refresh_all()
        self._save()

    def rename_category(self, cid: str):
        cat = self.state.category_by_id(cid)
        if cat is None:
            return
        name, ok = QInputDialog.getText(
            self, "Ganti Nama Kategori", "Nama kategori:", text=cat.name
        )
        if not ok:
            return
        name = name.strip()
        if not name or name == cat.name:
            return
        cat.name = name  # kode kategori tetap
        self._refresh_all()
        self._save()

    def delete_category(self, cid: str):
        cat = self.state.category_by_id(cid)
        if cat is None:
            return
        ret = QMessageBox.question(
            self, "Hapus Kategori",
            f"Hapus kategori \"{cat.name}\"?\n{len(cat.song_ids)} lagu kembali ke File Masuk.\n"
            f"Kode {cat.code} tidak akan dipakai lagi.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        self.state.inbox.extend(cat.song_ids)
        self.state.categories.remove(cat)
        self._refresh_all()
        self._save()

    # ================= Terapkan / Undo =================
    def choose_destination(self):
        start = self.state.destination or str(Path.home())
        d = QFileDialog.getExistingDirectory(self, "Pilih Folder Hasil", start)
        if d:
            self.state.destination = d
            self._save()
            self._refresh_all()

    def apply(self):
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, "Sedang Diproses", "Tunggu pemrosesan selesai.")
            return
        rows = [r for r in self._compute_rows() if r["kind"] == "cat"]
        if not rows:
            QMessageBox.information(
                self, "Belum Ada File",
                "Seret file MIDI ke kategori terlebih dahulu."
            )
            return

        over = sorted({r["category"] for r in rows
                       if r["order"] > naming.MAX_SONGS_PER_CATEGORY})
        if over:
            QMessageBox.warning(
                self, "Batas 99 Lagu",
                "Kategori berikut melebihi batas 99 lagu:\n- " + "\n- ".join(over) +
                "\n\nNomor tidak dibuat agar tidak ambigu. Kurangi jumlah lagu "
                "atau pecah ke kategori lain.",
            )
            return

        missing = [r for r in rows if not r["source"].exists()]
        if missing:
            ret = QMessageBox.question(
                self, "File Sumber Hilang",
                f"{len(missing)} file sumber tidak ditemukan di disk dan akan gagal diproses. Lanjutkan?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ret != QMessageBox.StandardButton.Yes:
                return

        if not self.state.destination or not Path(self.state.destination).is_dir():
            self.choose_destination()
        if not self.state.destination or not Path(self.state.destination).is_dir():
            QMessageBox.warning(self, "Folder Hasil", "Pilih folder hasil terlebih dahulu.")
            return
        dest = Path(self.state.destination)

        # Deteksi konflik SEBELUM menyalin
        counts = Counter(r["target_name"].lower() for r in rows)
        disk_conf: set[str] = set()
        for r in rows:
            tgt = dest / r["target_name"]
            if not tgt.exists():
                continue
            try:
                same = r["source"].samefile(tgt)
            except OSError:
                same = False
            if not same:
                disk_conf.add(r["target_name"])
        dup_conf = sorted({r["target_name"] for r in rows
                           if counts[r["target_name"].lower()] > 1})

        mode = "rename"
        if disk_conf or dup_conf:
            lines = [f"{n} — sudah ada di folder hasil" for n in sorted(disk_conf)]
            lines += [f"{n} — dipakai lebih dari satu file" for n in dup_conf]
            dlg = ConflictDialog(lines, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            mode = dlg.mode()

        tasks = [
            CopyTask(
                file_id=r["file_id"], source=r["source"],
                target=dest / r["target_name"], target_name=r["target_name"],
                category_name=r["category"], order=r["order"],
            )
            for r in rows
        ]
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_root = storage.BACKUP_DIR / stamp

        self.apply_btn.setEnabled(False)
        self.progress_label.setText("Menyiapkan…")
        self.worker = CopyWorker(tasks, mode, backup_root)
        self.worker.progress.connect(self._on_progress)
        self.worker.all_done.connect(lambda actions: self._on_apply_done(actions, backup_root))
        self.worker.start()

    def _on_progress(self, done: int, total: int, name: str):
        self.progress_label.setText(f"Menyalin {min(done + 1, total)}/{total}: {name}")

    def _on_apply_done(self, actions: list, backup_root: Path):
        w = self.worker
        self.worker = None
        if w is not None:
            w.wait()
            w.deleteLater()
        self.apply_btn.setEnabled(True)
        self.progress_label.setText("")

        counts = Counter(a["status"] for a in actions)
        op = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "destination": self.state.destination,
            "backup_root": str(backup_root),
            "actions": actions,
        }
        self.state.history = (self.state.history + [op])[-20:]
        self._save()
        self.log.appendPlainText(
            f"[{op['time']}] Diproses ke {op['destination']} — "
            + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
        )
        dlg = ReportDialog(actions, self.state.destination, self)
        dlg.exec()
        if dlg.clear_requested():
            self.state.inbox.clear()
            for c in self.state.categories:
                c.song_ids.clear()
            self.state.files.clear()
            self._save()
        self._refresh_all()

    def undo_last(self):
        if not self.state.history:
            QMessageBox.information(self, "Undo", "Tidak ada hasil pemrosesan untuk dibatalkan.")
            return
        op = self.state.history[-1]
        n = len(op.get("actions", []))
        ret = QMessageBox.question(
            self, "Batalkan Hasil Terakhir",
            f"Hapus hasil pemrosesan terakhir ({op.get('time', '?')}, {n} file) "
            "dan pulihkan file yang ditimpa?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        try:
            lines = perform_undo(op)
        except Exception as exc:
            lines = [f"Gagal undo: {exc}"]
        self.state.history = self.state.history[:-1]
        self._save()
        self.log.appendPlainText(
            "[undo] " + (" | ".join(lines) if lines else "Tidak ada perubahan.")
        )
        self._refresh_all()

    # ================= Lain-lain =================
    def _save(self):
        try:
            storage.save_state(self.state)
        except Exception as exc:
            self.log.appendPlainText(f"Gagal menyimpan konfigurasi: {exc}")

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            event.ignore()
            QMessageBox.warning(
                self, "Sedang Diproses",
                "Tunggu pemrosesan selesai sebelum menutup aplikasi."
            )
            return
        self._save()
        super().closeEvent(event)