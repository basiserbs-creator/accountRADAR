"""
PlaceholderImageBox: het afbeeldingsvak-vaktype van vdp4free.
"""

import uuid

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsTextItem,
    QMenu,
)


class PlaceholderImageBox(QGraphicsRectItem):
    """
    Een verplaatsbaar EN vergrootbaar afbeeldingsvak. Toont een echte
    afbeelding zodra het gekoppeld is aan een kolom die een bestandsnaam
    bevat en dat bestand gevonden kan worden (relatief aan de map van de
    geladen CSV/Excel, of als absoluut pad).

    De afbeelding wordt altijd volledig zichtbaar geschaald binnen het
    vak, met behoud van verhouding ("contain" - nooit bijgesneden, nooit
    vervormd).

    Ontbreekt het bestand of is het ongeldig, dan wordt NOOIT stilzwijgend
    niets getoond: het vak toont een duidelijke waarschuwingstekst en
    krijgt een rode rand (zelfde principe als bij tekstoverflow).
    """

    NORMAL_PEN = QPen(QColor(180, 120, 30), 1)
    OVERFLOW_PEN = QPen(QColor(220, 30, 30), 2)
    RESIZE_HANDLE_SIZE = 10
    MIN_BOX_WIDTH = 30
    MIN_BOX_HEIGHT = 30

    def __init__(self, x=20, y=20, width=140, height=100, field_name=None, element_id=None):
        super().__init__(0, 0, width, height)
        self.setPos(x, y)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setBrush(QBrush(QColor(255, 250, 235, 210)))
        self.setPen(self.NORMAL_PEN)

        self.element_id = element_id or str(uuid.uuid4())
        self.stack_order = 0  # onderlinge volgorde bij gelijke z-waarde
        self.locked = False  # zie set_locked()

        self.field_name = field_name
        self._is_overflowing = False  # hier: "afbeelding ontbreekt/ongeldig"
        self._canvas = None  # wordt gezet door CanvasView bij aanmaken
        self._original_pixmap = QPixmap()
        self.crop_shape = "none"  # "none" | "circle" - zie _rescale_pixmap
        self._resizing = False
        self._resize_start_scene_pos = None
        self._resize_start_rect = None

        self.label_item = QGraphicsTextItem(self)
        self.label_item.setDefaultTextColor(QColor(120, 90, 20))

        self.pixmap_item = QGraphicsPixmapItem(self)
        self.pixmap_item.setVisible(False)

        # Sleephoekje als apart kind-element met hoge z-waarde, zodat het
        # altijd zichtbaar/bruikbaar blijft - ook bij een afbeelding die
        # het hele vak vult (anders zou de pixmap het hoekje bedekken).
        self.handle_item = QGraphicsRectItem(
            0, 0, self.RESIZE_HANDLE_SIZE, self.RESIZE_HANDLE_SIZE, self
        )
        self.handle_item.setBrush(QBrush(QColor(180, 120, 30)))
        self.handle_item.setPen(Qt.PenStyle.NoPen)
        self.handle_item.setZValue(10)
        self.handle_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._position_handle()

        self.show_placeholder()

    def _position_handle(self):
        r = self.rect()
        self.handle_item.setPos(
            r.width() - self.RESIZE_HANDLE_SIZE, r.height() - self.RESIZE_HANDLE_SIZE
        )

    # ------------------------------------------------------------------
    # Resize-hoekje: zelfde interactie als bij PlaceholderTextBox
    def _is_in_resize_handle(self, pos):
        r = self.rect()
        handle = QRectF(
            r.width() - self.RESIZE_HANDLE_SIZE,
            r.height() - self.RESIZE_HANDLE_SIZE,
            self.RESIZE_HANDLE_SIZE,
            self.RESIZE_HANDLE_SIZE,
        )
        return handle.contains(pos)

    def set_locked(self, locked: bool):
        """
        Vergrendelt/ontgrendelt dit vak. Een vergrendeld vak kan nog wel
        geselecteerd worden (bv. om te ontgrendelen), maar niet meer
        versleept, geresized of verwijderd - voorkomt per ongeluk
        wijzigen van een vak dat "af" is.
        """
        self.locked = locked
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not locked)

    def mousePressEvent(self, event):
        if self.locked:
            # Selecteren mag nog (bv. om te ontgrendelen via het
            # rechtsklikmenu), maar geen slepen/resizen.
            super().mousePressEvent(event)
            return
        # Voor undo/redo: leg de staat vast VOORDAT een sleep-/resize-actie
        # begint. Een simpele klik-zonder-slepen zet ook een (dan
        # inhoudelijk identieke) snapshot op de stack - onschuldig, maar
        # wel een bewuste vereenvoudiging t.o.v. per-actie undo-commando's.
        if self._canvas is not None:
            self._canvas.capture_undo_point()
        if self._is_in_resize_handle(event.pos()):
            self._resizing = True
            self._resize_start_scene_pos = event.scenePos()
            self._resize_start_rect = self.rect()
            event.accept()
            return
        self._resizing = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            delta = event.scenePos() - self._resize_start_scene_pos
            new_width = max(self.MIN_BOX_WIDTH, self._resize_start_rect.width() + delta.x())
            new_height = max(self.MIN_BOX_HEIGHT, self._resize_start_rect.height() + delta.y())
            self.prepareGeometryChange()
            self.setRect(0, 0, new_width, new_height)
            self._center_label()
            self._rescale_pixmap()
            self._position_handle()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # Meldt de wijziging aan MainWindow (dirty-state) na afloop van
        # ZOWEL een resize ALS een normale verplaatsing (die laatste
        # verloopt via Qt's ingebouwde ItemIsMovable-afhandeling in
        # super().mouseReleaseEvent(), vandaar dat dit na beide takken
        # gebeurt i.p.v. alleen in de resize-tak).
        was_resizing = self._resizing
        if was_resizing:
            self._resizing = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)
        if self._canvas is not None:
            self._canvas.notify_changed()

    def contextMenuEvent(self, event):
        menu = QMenu()

        none_action = menu.addAction("Vorm: Rechthoek (geen bijsnijden)")
        none_action.setCheckable(True)
        none_action.setChecked(self.crop_shape == "none")

        circle_action = menu.addAction("Vorm: Rond bijsnijden")
        circle_action.setCheckable(True)
        circle_action.setChecked(self.crop_shape == "circle")

        menu.addSeparator()
        front_action = menu.addAction("Naar voren brengen")
        back_action = menu.addAction("Naar achteren plaatsen")

        menu.addSeparator()
        lock_action = menu.addAction("Ontgrendelen" if self.locked else "Vergrendelen")
        delete_action = menu.addAction("Verwijderen")
        delete_action.setEnabled(not self.locked)

        chosen = menu.exec(event.screenPos())
        if chosen is not None and self._canvas is not None:
            self._canvas.capture_undo_point()

        if chosen == none_action:
            self.crop_shape = "none"
            self._rescale_pixmap()
        elif chosen == circle_action:
            self.crop_shape = "circle"
            self._rescale_pixmap()
        elif chosen == front_action:
            if self._canvas is not None:
                self._canvas.bring_to_front(self)
                self._canvas.notify_changed()
        elif chosen == back_action:
            if self._canvas is not None:
                self._canvas.send_to_back(self)
                self._canvas.notify_changed()
        elif chosen == lock_action:
            self.set_locked(not self.locked)
            if self._canvas is not None:
                self._canvas.notify_changed()
        elif chosen == delete_action:
            scene = self.scene()
            if scene is not None:
                scene.removeItem(self)
            if self._canvas is not None:
                self._canvas.notify_changed()

    # ------------------------------------------------------------------
    def set_field(self, field_name: str):
        """Koppelt dit vak aan een kolomnaam (die bestandsnamen bevat)."""
        self.field_name = field_name
        # De daadwerkelijke afbeelding wordt getoond zodra MainWindow
        # hierna apply_record() aanroept.

    def show_placeholder(self):
        """Sjabloonweergave: geen echte afbeelding, alleen een label."""
        self.pixmap_item.setVisible(False)
        self.label_item.setVisible(True)
        if self.field_name:
            self.label_item.setPlainText("🖼 {{" + self.field_name + "}}")
        else:
            self.label_item.setPlainText("🖼 afbeeldingsvak")
        self.label_item.setDefaultTextColor(QColor(120, 90, 20))
        self._is_overflowing = False
        self._center_label()
        self._update_style()

    def show_value(self, value):
        """Laadt en toont de echte afbeelding voor het huidige record."""
        filename = "" if value is None else str(value).strip()
        if not filename:
            self._show_missing("(leeg veld)")
            return

        path = self._canvas.resolve_asset_path(filename) if self._canvas else None
        pixmap = QPixmap(path) if path else QPixmap()

        if pixmap.isNull():
            self._show_missing(filename)
            return

        self._original_pixmap = pixmap
        self.label_item.setVisible(False)
        self.pixmap_item.setVisible(True)
        self._rescale_pixmap()
        self._is_overflowing = False
        self._update_style()

    def _show_missing(self, filename):
        self._original_pixmap = QPixmap()
        self.pixmap_item.setVisible(False)
        self.label_item.setVisible(True)
        self.label_item.setPlainText(f"⚠ niet gevonden:\n{filename}")
        self.label_item.setDefaultTextColor(QColor(180, 30, 30))
        self._is_overflowing = True
        self._center_label()
        self._update_style()

    def mark_missing_column(self):
        """Structurele waarschuwing: gekoppelde kolom bestaat niet in de dataset."""
        self._show_missing(f"kolom '{self.field_name}' bestaat niet")

    def _rescale_pixmap(self):
        if not self.pixmap_item.isVisible() or self._original_pixmap.isNull():
            return
        available_w = max(self.rect().width(), 1)
        available_h = max(self.rect().height(), 1)
        scaled = self._original_pixmap.scaled(
            int(available_w),
            int(available_h),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if self.crop_shape == "circle":
            scaled = self._apply_circular_mask(scaled)
        self.pixmap_item.setPixmap(scaled)
        # Centreren binnen het vak
        offset_x = (available_w - scaled.width()) / 2
        offset_y = (available_h - scaled.height()) / 2
        self.pixmap_item.setPos(offset_x, offset_y)

    @staticmethod
    def _apply_circular_mask(pixmap: QPixmap) -> QPixmap:
        """
        Snijdt een pixmap bij tot een ellips die precies binnen de huidige
        afmetingen past (wordt een echte cirkel als het vak vierkant is -
        net als bij de QR-code kiest de gebruiker daarvoor bewust een
        vierkant vak). De rest van de pixmap wordt transparant.
        """
        size = pixmap.size()
        masked = QPixmap(size)
        masked.fill(Qt.GlobalColor.transparent)

        painter = QPainter(masked)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, size.width(), size.height())
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

        return masked

    def _center_label(self):
        self.label_item.setTextWidth(max(self.rect().width() - 8, 10))
        self.label_item.setPos(4, 4)

    def _update_style(self):
        self.setPen(self.OVERFLOW_PEN if self._is_overflowing else self.NORMAL_PEN)


