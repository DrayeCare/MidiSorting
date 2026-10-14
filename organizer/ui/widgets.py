"""Widget drag-and-drop: daftar serbaguna, panel File Masuk, kartu kategori."""
from __future__ import annotations

import json

from PySide6.QtCore import Qt, QMimeData, Signal
from PySide6.QtGui import QBrush, QColor, QDrag
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QGroupBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QToolButton, QVBoxLayout,
)

MIME_TYPE = "application/x-midi-organizer-ids"
ROLE_FILE_ID = Qt.ItemDataRole.UserRole


def make_item(file_id: str | None, label: str, tooltip: str = "") -> QListWidgetItem:
    it = QListWidgetItem(label)
    if file_id:
        it.setData(ROLE_FILE_ID, file_id)
        it.setFlags(
            Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsDragEnabled
        )
    else:  # placeholder saat daftar kosong
        it.setFlags(Qt.ItemFlag.ItemIsEnabled)
        it.setForeground(QBrush(QColor("#8a8a8a")))
    if tooltip:
        it.setToolTip(tooltip)
    return it


class DragList(QListWidget):
    """Daftar yang mendukung drag internal (pindah/urutkan) dan drop dari Explorer."""

    filesDropped = Signal(list)          # path dari Explorer
    idsDropped = Signal(str, list, int)  # target_key, id file, baris sisip
    deletePressed = Signal(list)

    def __init__(self, target_key: str, accept_files: bool = False, parent=None):
        super().__init__(parent)
        self.target_key = target_key
        self.accept_files = accept_files
        self.setMinimumHeight(110)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    # ---------- drag keluar ----------
    def startDrag(self, supportedActions):
        ids = [it.data(ROLE_FILE_ID) for it in self.selectedItems()]
        ids = [i for i in ids if i]
        if not ids:
            return
        mime = QMimeData()
        mime.setData(MIME_TYPE, json.dumps(ids).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    # ---------- drop masuk ----------
    def _can_accept(self, mime: QMimeData) -> bool:
        if mime.hasFormat(MIME_TYPE):
            return True
        return self.accept_files and mime.hasUrls()

    def dragEnterEvent(self, event):
        if self._can_accept(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._can_accept(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        mime = event.mimeData()
        if mime.hasFormat(MIME_TYPE):
            try:
                ids = json.loads(bytes(mime.data(MIME_TYPE)).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                event.ignore()
                return
            self.idsDropped.emit(self.target_key, ids, self._drop_row(event))
            event.acceptProposedAction()
            return
        if self.accept_files and mime.hasUrls():
            paths = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
            if paths:
                self.filesDropped.emit(paths)
            event.acceptProposedAction()
            return
        event.ignore()

    def _drop_row(self, event) -> int:
        pos = event.position().toPoint()
        item = self.itemAt(pos)
        if item is None:
            return self.count()
        row = self.row(item)
        if pos.y() > self.visualItemRect(item).center().y():
            row += 1
        return row

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            ids = [it.data(ROLE_FILE_ID) for it in self.selectedItems()]
            ids = [i for i in ids if i]
            if ids:
                self.deletePressed.emit(ids)
                return
        super().keyPressEvent(event)


class InboxPanel(QGroupBox):
    filesDropped = Signal(list)
    idsDropped = Signal(list, int)
    deletePressed = Signal(list)

    def __init__(self, parent=None):
        super().__init__("File Masuk", parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.list = DragList("inbox", accept_files=True)
        self.list.setToolTip("Seret file .mid / .midi dari File Explorer ke sini.")
        lay.addWidget(self.list, 1)
        self.count_label = QLabel("0 file")
        lay.addWidget(self.count_label)
        self.list.filesDropped.connect(self.filesDropped)
        self.list.idsDropped.connect(lambda key, ids, row: self.idsDropped.emit(ids, row))
        self.list.deletePressed.connect(self.deletePressed)

    def set_files(self, rows):
        self.list.clear()
        for fid, label, tip in rows:
            self.list.addItem(make_item(fid, label, tip))
        if not rows:
            self.list.addItem(make_item(None, "Seret file MIDI ke sini…"))
        self.count_label.setText(f"{len(rows)} file")


class CategoryCard(QFrame):
    idsDropped = Signal(str, list, int)
    filesDropped = Signal(str, list)
    renameRequested = Signal(str)
    deleteRequested = Signal(str)
    deletePressed = Signal(str, list)

    def __init__(self, category_id: str, code: int, name: str, parent=None):
        super().__init__(parent)
        self.category_id = category_id
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)

        self.name_label = QLabel(f"<b>{name}</b>")
        self.code_label = QLabel(f"kode {code}")
        self.count_label = QLabel("0 lagu")

        btn_rename = QToolButton()
        btn_rename.setText("✎")
        btn_rename.setToolTip("Ganti nama kategori (kode tidak berubah)")
        btn_delete = QToolButton()
        btn_delete.setText("✕")
        btn_delete.setToolTip("Hapus kategori (lagu kembali ke File Masuk)")

        header = QHBoxLayout()
        header.addWidget(self.name_label)
        header.addWidget(self.code_label)
        header.addStretch(1)
        header.addWidget(self.count_label)
        header.addWidget(btn_rename)
        header.addWidget(btn_delete)

        self.list = DragList(category_id, accept_files=True)
        self.list.setToolTip(
            "Seret file .mid/.midi dari Explorer ke sini, atau pindahkan/urutkan "
            "file dari panel dan kategori lain."
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addLayout(header)
        lay.addWidget(self.list, 1)

        self.list.idsDropped.connect(self.idsDropped)
        self.list.filesDropped.connect(
            lambda paths: self.filesDropped.emit(self.category_id, paths)
        )
        self.list.deletePressed.connect(
            lambda ids: self.deletePressed.emit(self.category_id, ids)
        )
        btn_rename.clicked.connect(lambda: self.renameRequested.emit(self.category_id))
        btn_delete.clicked.connect(lambda: self.deleteRequested.emit(self.category_id))

    def set_header(self, name: str, code: int):
        self.name_label.setText(f"<b>{name}</b>")
        self.code_label.setText(f"kode {code}")

    def set_songs(self, rows):
        self.list.clear()
        for fid, label, tip in rows:
            self.list.addItem(make_item(fid, label, tip))
        if not rows:
            self.list.addItem(make_item(None, "Seret file ke kategori ini…"))
        self.count_label.setText(f"{len(rows)} lagu")