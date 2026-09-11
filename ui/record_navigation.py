"""
RecordNavigationBar: onderbalk om door records te bladeren.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class RecordNavigationBar(QWidget):
    """
    Onderbalk: bladeren door records voor de live preview.
    Zendt signalen uit, de daadwerkelijke navigatielogica (welke index,
    welk record) zit in MainWindow.
    """

    previous_requested = Signal()
    next_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.status_label = QLabel("Geen data geladen")
        layout.addWidget(self.status_label)
        layout.addStretch()

        self.previous_button = QPushButton("◀ Vorige")
        self.previous_button.clicked.connect(self.previous_requested)
        self.previous_button.setEnabled(False)
        layout.addWidget(self.previous_button)

        self.position_label = QLabel("")
        self.position_label.setMinimumWidth(110)
        self.position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.position_label)

        self.next_button = QPushButton("Volgende ▶")
        self.next_button.clicked.connect(self.next_requested)
        self.next_button.setEnabled(False)
        layout.addWidget(self.next_button)

    def set_loaded(self, filename: str, column_count: int, record_count: int):
        self.status_label.setText(f"{filename} - {column_count} kolommen")
        has_records = record_count > 0
        self.previous_button.setEnabled(has_records)
        self.next_button.setEnabled(has_records)

    def set_position(self, index: int, total: int):
        """index is 0-based; label toont 1-based aan de gebruiker."""
        if total == 0:
            self.position_label.setText("")
            return
        self.position_label.setText(f"Record {index + 1} van {total}")
        self.previous_button.setEnabled(index > 0)
        self.next_button.setEnabled(index < total - 1)


