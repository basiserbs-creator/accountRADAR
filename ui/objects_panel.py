"""
ObjectsPanel: linkerpaneel dat een interactieve lijst van objecten/vakken
toont. Elk vak op het canvas krijgt hier een regel, gesorteerd van
BOVENSTE naar ONDERSTE laag (zoals ze zichtbaar over elkaar liggen).

Interactie:
- Klikken op een regel selecteert het bijbehorende vak op het canvas.
- Slepen om de volgorde te wijzigen past de laagvolgorde aan (stuurt
  order_changed uit met de nieuwe boven-naar-onder-volgorde).
- Maskeervlakken krijgen een kleurvoorbeeldje i.p.v. alleen een hex-code.
- Een vergrendeld vak krijgt een slotje voor het label.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QAbstractItemView, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget


class ObjectsPanel(QWidget):
    """Linkerpaneel: interactieve lijst van objecten/layers op de huidige pagina."""

    # Uitgezonden wanneer de gebruiker op een regel klikt die een echt
    # vak vertegenwoordigt (dus niet de vaste "Background"-regel).
    item_selected = Signal(object)
    # Uitgezonden na het slepen van een regel naar een nieuwe positie -
    # geeft de volledige, nieuwe boven-naar-onder-volgorde van vakken door.
    order_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Objecten</b>"))

        self.object_list = QListWidget()
        self.object_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.object_list.itemClicked.connect(self._on_item_clicked)
        self.object_list.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self.object_list)

        self._suppress_signals = False

    # ------------------------------------------------------------------
    def set_objects(self, entries: list[tuple[str, object]]):
        """
        Bouwt de lijst opnieuw op vanuit `entries`: een lijst van
        (label, vak)-tupels, BOVENSTE laag eerst. Geef voor de vaste
        achtergrond-regel `None` als vak op - die regel is dan niet
        sleepbaar en selecteert niets.
        """
        self._suppress_signals = True
        self.object_list.clear()
        for label, box in entries:
            display_label = label
            if box is not None and getattr(box, "locked", False):
                display_label = f"🔒 {display_label}"
            item = QListWidgetItem(display_label)
            item.setData(Qt.ItemDataRole.UserRole, box)

            color = getattr(box, "color", None)
            if color:
                swatch = QPixmap(14, 14)
                swatch.fill(QColor(color))
                item.setIcon(QIcon(swatch))

            if box is None:
                # De achtergrond-regel: niet sleepbaar, puur informatief.
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)

            self.object_list.addItem(item)
        self._suppress_signals = False

    def highlight_box(self, box):
        """
        Selecteert (markeert) de regel die bij `box` hoort, zonder dat dit
        zelf weer een item_selected-signaal veroorzaakt (voorkomt een
        oneindige heen-en-weer-lus met de canvas-selectie). Geef None om
        de markering op te heffen.
        """
        self._suppress_signals = True
        self.object_list.clearSelection()
        if box is not None:
            for i in range(self.object_list.count()):
                item = self.object_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) is box:
                    item.setSelected(True)
                    self.object_list.scrollToItem(item)
                    break
        self._suppress_signals = False

    # ------------------------------------------------------------------
    def _on_item_clicked(self, item):
        if self._suppress_signals:
            return
        box = item.data(Qt.ItemDataRole.UserRole)
        if box is not None:
            self.item_selected.emit(box)

    def _on_rows_moved(self, *args):
        if self._suppress_signals:
            return
        boxes = []
        for i in range(self.object_list.count()):
            item = self.object_list.item(i)
            box = item.data(Qt.ItemDataRole.UserRole)
            if box is not None:
                boxes.append(box)
        self.order_changed.emit(boxes)
