"""
ShapeMaskBox: het maskeervlak-vaktype van vdp4free (statisch, geen
datakoppeling - bedoeld om een deel van de PDF-achtergrond af te dekken).
"""

import uuid

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QColorDialog, QGraphicsItem, QGraphicsRectItem, QMenu


class ShapeMaskBox(QGraphicsRectItem):
    """
    Een verplaatsbaar EN vergrootbaar maskeervlak: een ondoorzichtige,
    effen gekleurde rechthoek die je over de PDF-achtergrond legt om een
    deel ervan af te dekken (bv. een voorbedrukt logo of oud adresvak).

    Geen datakoppeling - dit is een puur statisch opmaakelement, geen
    placeholder. Staat altijd boven de achtergrond (die een vaste lage
    z-waarde heeft), dus dekt automatisch af wat eronder ligt.

    Randstijl instelbaar via rechtsklik: gestippeld (standaard, handig om
    een wit vlak op een witte achtergrond nog te kunnen selecteren),
    effen, of geen rand. Het sleephoekje blijft ALTIJD zichtbaar,
    ongeacht de randkeuze - anders zou "geen rand" het vak onbruikbaar
    maken om te verslepen/resizen.
    """

    BORDER_PENS = {
        "dashed": QPen(QColor(90, 90, 90), 1, Qt.PenStyle.DashLine),
        "solid": QPen(QColor(90, 90, 90), 1, Qt.PenStyle.SolidLine),
        "none": QPen(Qt.PenStyle.NoPen),
    }
    RESIZE_HANDLE_SIZE = 10
    MIN_BOX_WIDTH = 10
    MIN_BOX_HEIGHT = 10

    def __init__(
        self,
        x=20,
        y=20,
        width=120,
        height=60,
        color="#ffffff",
        border_style="dashed",
        element_id=None,
    ):
        super().__init__(0, 0, width, height)
        self.setPos(x, y)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.color = color
        self.border_style = border_style  # "dashed" | "solid" | "none"
        self.setBrush(QBrush(QColor(color)))
        self.setPen(self.BORDER_PENS[self.border_style])

        self.element_id = element_id or str(uuid.uuid4())

        self._canvas = None  # wordt gezet door CanvasView bij aanmaken
        self._resizing = False
        self._resize_start_scene_pos = None
        self._resize_start_rect = None

        # Sleephoekje als apart kind-element met hoge z-waarde - blijft
        # zichtbaar/bruikbaar ongeacht de randkeuze (ook bij "geen rand").
        self.handle_item = QGraphicsRectItem(
            0, 0, self.RESIZE_HANDLE_SIZE, self.RESIZE_HANDLE_SIZE, self
        )
        self.handle_item.setBrush(QBrush(QColor(90, 90, 90)))
        self.handle_item.setPen(Qt.PenStyle.NoPen)
        self.handle_item.setZValue(10)
        self.handle_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._position_handle()

    def _position_handle(self):
        r = self.rect()
        self.handle_item.setPos(
            r.width() - self.RESIZE_HANDLE_SIZE, r.height() - self.RESIZE_HANDLE_SIZE
        )

    def set_border_style(self, style: str):
        self.border_style = style
        self.setPen(self.BORDER_PENS[style])

    # ------------------------------------------------------------------
    # Resize-hoekje: zelfde interactie als de andere vaktypes
    def _is_in_resize_handle(self, pos):
        r = self.rect()
        handle = QRectF(
            r.width() - self.RESIZE_HANDLE_SIZE,
            r.height() - self.RESIZE_HANDLE_SIZE,
            self.RESIZE_HANDLE_SIZE,
            self.RESIZE_HANDLE_SIZE,
        )
        return handle.contains(pos)

    def mousePressEvent(self, event):
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
        color_action = menu.addAction("Kleur instellen...")

        menu.addSeparator()
        border_menu = menu.addMenu("Randstijl")
        dashed_action = border_menu.addAction("Gestippeld")
        dashed_action.setCheckable(True)
        dashed_action.setChecked(self.border_style == "dashed")
        solid_action = border_menu.addAction("Effen")
        solid_action.setCheckable(True)
        solid_action.setChecked(self.border_style == "solid")
        none_border_action = border_menu.addAction("Geen rand")
        none_border_action.setCheckable(True)
        none_border_action.setChecked(self.border_style == "none")

        menu.addSeparator()
        front_action = menu.addAction("Naar voren brengen")
        back_action = menu.addAction("Naar achteren plaatsen")

        menu.addSeparator()
        delete_action = menu.addAction("Verwijderen")

        chosen = menu.exec(event.screenPos())
        if chosen is not None and self._canvas is not None:
            self._canvas.capture_undo_point()

        if chosen == color_action:
            chosen_color = QColorDialog.getColor(QColor(self.color), None, "Maskerkleur kiezen")
            if chosen_color.isValid():
                self.color = chosen_color.name()
                self.setBrush(QBrush(QColor(self.color)))
                if self._canvas is not None:
                    self._canvas.notify_changed()
        elif chosen == dashed_action:
            self.set_border_style("dashed")
            if self._canvas is not None:
                self._canvas.notify_changed()
        elif chosen == solid_action:
            self.set_border_style("solid")
            if self._canvas is not None:
                self._canvas.notify_changed()
        elif chosen == none_border_action:
            self.set_border_style("none")
            if self._canvas is not None:
                self._canvas.notify_changed()
        elif chosen == front_action:
            if self._canvas is not None:
                self._canvas.bring_to_front(self)
                self._canvas.notify_changed()
        elif chosen == back_action:
            if self._canvas is not None:
                self._canvas.send_to_back(self)
                self._canvas.notify_changed()
        elif chosen == delete_action:
            scene = self.scene()
            if scene is not None:
                scene.removeItem(self)
            if self._canvas is not None:
                self._canvas.notify_changed()


