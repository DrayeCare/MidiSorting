"""Dialog konflik nama dan laporan pemrosesan."""
from __future__ import annotations

from collections import Counter

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel,
    QListWidget, QPushButton, QRadioButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)

STATUS_LABELS = {
    "copied": "Disalin",
    "overwritten": "Timpa (lama dicadangkan)",
    "renamed": "Disalin (nama alternatif)",
    "skipped": "Dilewati",
    "unchanged": "Sudah sesuai",
    "failed": "Gagal",
}


class ConflictDialog(QDialog):
    MODE_SKIP = "skip"
    MODE_OVERWRITE = "overwrite"
    MODE_RENAME = "rename"

    def __init__(self, conflicts: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Konflik Nama File")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            "Ada nama file hasil yang bentrok:\n"
            "• sudah ada di folder hasil, atau\n"
            "• dipakai lebih dari satu file dalam daftar.\n\n"
            "Pilih cara penanganan:"
        ))
        lst = QListWidget()
        lst.setMaximumHeight(200)
        for c in conflicts[:300]:
            lst.addItem(c)
        if len(conflicts) > 300:
            lst.addItem(f"… dan {len(conflicts) - 300} konflik lainnya")
        lay.addWidget(lst)

        self.rb_skip = QRadioButton("Lewati file yang bentrok (tidak disalin)")
        self.rb_over = QRadioButton("Timpa nama di folder hasil (file lama disimpan ke cadangan)")
        self.rb_rename = QRadioButton("Beri nama alternatif otomatis, mis. 101 - Lagu (2).mid")
        self.rb_rename.setChecked(True)
        lay.addWidget(self.rb_skip)
        lay.addWidget(self.rb_over)
        lay.addWidget(self.rb_rename)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def mode(self) -> str:
        if self.rb_skip.isChecked():
            return self.MODE_SKIP
        if self.rb_over.isChecked():
            return self.MODE_OVERWRITE
        return self.MODE_RENAME


class ReportDialog(QDialog):
    def __init__(self, actions: list[dict], destination: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Laporan Pemrosesan")
        self.resize(680, 460)
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel(f"Folder tujuan: {destination}"))
        counts = Counter(a["status"] for a in actions)
        summary = " · ".join(
            f"{STATUS_LABELS.get(k, k)}: {v}" for k, v in sorted(counts.items())
        )
        lay.addWidget(QLabel(f"<b>Hasil:</b> {summary}"))

        table = QTableWidget(len(actions), 3)
        table.setHorizontalHeaderLabels(["Status", "Nama Hasil", "Keterangan"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i, a in enumerate(actions):
            vals = [STATUS_LABELS.get(a["status"], a["status"]),
                    a.get("final_name", a.get("planned_name", "")),
                    a.get("message", "")]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                table.setItem(i, c, it)
        table.resizeColumnsToContents()
        lay.addWidget(table, 1)

        self.chk_clear = QCheckBox(
            "Kosongkan daftar file di aplikasi setelah ini (file sumber tidak diubah)"
        )
        lay.addWidget(self.chk_clear)

        row = QHBoxLayout()
        btn_open = QPushButton("Buka Folder Hasil")
        btn_open.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(destination))
        )
        row.addWidget(btn_open)
        row.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        row.addWidget(bb)
        lay.addLayout(row)

    def clear_requested(self) -> bool:
        return self.chk_clear.isChecked()