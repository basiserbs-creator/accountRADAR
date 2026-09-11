"""
ObjectsPanel: linkerpaneel dat een lijst van objecten/vakken toont.
"""

from PySide6.QtWidgets import QLabel, QListWidget, QVBoxLayout, QWidget


class ObjectsPanel(QWidget):
    """Linkerpaneel: lijst van objecten/layers op de huidige pagina."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Objecten</b>"))

        self.object_list = QListWidget()
        layout.addWidget(self.object_list)


