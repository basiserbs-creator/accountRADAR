"""
PlaceholderBarcodeBox: het barcode/QR-vaktype van vdp4free.
Gebruikt de gratis/open-source libraries `qrcode` en `python-barcode`
(beide MIT-licentie).
"""

import io
import uuid

import barcode
import qrcode
from barcode.writer import ImageWriter
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsTextItem,
    QMenu,
)


class PlaceholderBarcodeBox(QGraphicsRectItem):
    """
    Een verplaatsbaar EN vergrootbaar barcode/QR-vak. Genereert zelf een
    QR-code of een Code128-barcode op basis van de waarde in de
    gekoppelde kolom (via de gratis/open-source libraries `qrcode` en
    `python-barcode`, beide MIT-licentie).

    Type instelbaar via rechtsklikmenu: "qr" of "code128". Een QR-code
    wordt altijd vierkant weergegeven (voor leesbaarheid); een barcode
    schaalt gewoon mee met de breedte/hoogte van het vak.

    Lukt het genereren niet (bv. leeg veld, of een teken dat niet
    toegestaan is in Code128), dan wordt NOOIT stilzwijgend niets
    getoond: een duidelijke waarschuwing + rode rand, net als bij de
    andere vaktypes.
    """

    NORMAL_PEN = QPen(QColor(90, 90, 90), 1)
    OVERFLOW_PEN = QPen(QColor(220, 30, 30), 2)
    RESIZE_HANDLE_SIZE = 10
    MIN_BOX_WIDTH = 30
    MIN_BOX_HEIGHT = 30

    def __init__(
        self,
        x=20,
        y=20,
        width=100,
        height=100,
        field_name=None,
        barcode_type="qr",
        element_id=None,
    ):
        super().__init__(0, 0, width, height)
        self.setPos(x, y)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setBrush(QBrush(QColor(245, 245, 245, 210)))
        self.setPen(self.NORMAL_PEN)

        self.element_id = element_id or str(uuid.uuid4())

        self.field_name = field_name
        self.barcode_type = barcode_type  # "qr" | "code128"
        self._is_overflowing = False
        self._canvas = None
        self._original_pixmap = QPixmap()
        self._resizing = False
        self._resize_start_scene_pos = None
        self._resize_start_rect = None

        self.label_item = QGraphicsTextItem(self)
        self.label_item.setDefaultTextColor(QColor(90, 90, 90))

        self.pixmap_item = QGraphicsPixmapItem(self)
        self.pixmap_item.setVisible(False)

        # Sleephoekje als apart kind-element met hoge z-waarde - anders
        # zou een grote QR-code/barcode het hoekje volledig kunnen bedekken
        # (precies het gemelde probleem).
        self.handle_item = QGraphicsRectItem(
            0, 0, self.RESIZE_HANDLE_SIZE, self.RESIZE_HANDLE_SIZE, self
        )
        self.handle_item.setBrush(QBrush(QColor(90, 90, 90)))
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
        qr_action = menu.addAction("Type: QR-code")
        qr_action.setCheckable(True)
        qr_action.setChecked(self.barcode_type == "qr")

        code128_action = menu.addAction("Type: Barcode (Code128)")
        code128_action.setCheckable(True)
        code128_action.setChecked(self.barcode_type == "code128")

        menu.addSeparator()
        front_action = menu.addAction("Naar voren brengen")
        back_action = menu.addAction("Naar achteren plaatsen")

        menu.addSeparator()
        delete_action = menu.addAction("Verwijderen")

        chosen = menu.exec(event.screenPos())
        if chosen is not None and self._canvas is not None:
            self._canvas.capture_undo_point()

        if chosen == qr_action:
            self.barcode_type = "qr"
            self._regenerate_from_current_value()
        elif chosen == code128_action:
            self.barcode_type = "code128"
            self._regenerate_from_current_value()
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

    def _regenerate_from_current_value(self):
        """Na het wisselen van type: opnieuw genereren met de huidige recordwaarde."""
        if self._canvas is not None:
            record = self._canvas.get_current_record()
            if record is not None and self.field_name and self.field_name in record:
                self.show_value(record[self.field_name])
                return
        self.show_placeholder()

    # ------------------------------------------------------------------
    def set_field(self, field_name: str):
        """Koppelt dit vak aan een kolomnaam (de waarde wordt gecodeerd)."""
        self.field_name = field_name

    def show_placeholder(self):
        """Sjabloonweergave: geen echte code, alleen een label."""
        self.pixmap_item.setVisible(False)
        self.label_item.setVisible(True)
        type_label = "QR-code" if self.barcode_type == "qr" else "Barcode"
        if self.field_name:
            self.label_item.setPlainText(f"▦ {type_label}\n{{{{{self.field_name}}}}}")
        else:
            self.label_item.setPlainText(f"▦ {type_label}-vak")
        self.label_item.setDefaultTextColor(QColor(90, 90, 90))
        self._is_overflowing = False
        self._center_label()
        self._update_style()

    def show_value(self, value):
        """Genereert en toont de echte QR-code/barcode voor het huidige record."""
        text = "" if value is None else str(value).strip()
        if not text:
            self._show_error("(leeg veld)")
            return

        try:
            pixmap = self._generate_pixmap(text)
        except Exception as exc:  # noqa: BLE001 - elke genereerfout tonen, nooit crashen
            self._show_error(f"kon niet genereren ({exc})")
            return

        if pixmap is None or pixmap.isNull():
            self._show_error("kon niet genereren")
            return

        self._original_pixmap = pixmap
        self.label_item.setVisible(False)
        self.pixmap_item.setVisible(True)
        self._rescale_pixmap()
        self._is_overflowing = False
        self._update_style()

    def _generate_pixmap(self, text: str):
        buf = io.BytesIO()
        if self.barcode_type == "qr":
            img = qrcode.make(text)
            img.save(buf, format="PNG")
        else:  # code128
            code128_class = barcode.get_barcode_class("code128")
            obj = code128_class(text, writer=ImageWriter())
            obj.write(buf, options={"write_text": False})
        pixmap = QPixmap()
        pixmap.loadFromData(buf.getvalue())
        return pixmap

    def _show_error(self, message: str):
        self._original_pixmap = QPixmap()
        self.pixmap_item.setVisible(False)
        self.label_item.setVisible(True)
        self.label_item.setPlainText(f"⚠ {message}")
        self.label_item.setDefaultTextColor(QColor(180, 30, 30))
        self._is_overflowing = True
        self._center_label()
        self._update_style()

    def mark_missing_column(self):
        """Structurele waarschuwing: gekoppelde kolom bestaat niet in de dataset."""
        self._show_error(f"kolom '{self.field_name}' bestaat niet")

    def _rescale_pixmap(self):
        if not self.pixmap_item.isVisible() or self._original_pixmap.isNull():
            return
        available_w = max(self.rect().width(), 1)
        available_h = max(self.rect().height(), 1)

        if self.barcode_type == "qr":
            # QR-codes altijd vierkant weergeven, voor leesbaarheid/scanbaarheid
            side = min(available_w, available_h)
            target_w, target_h = side, side
        else:
            target_w, target_h = available_w, available_h

        scaled = self._original_pixmap.scaled(
            int(target_w),
            int(target_h),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.pixmap_item.setPixmap(scaled)
        offset_x = (available_w - scaled.width()) / 2
        offset_y = (available_h - scaled.height()) / 2
        self.pixmap_item.setPos(offset_x, offset_y)

    def _center_label(self):
        self.label_item.setTextWidth(max(self.rect().width() - 8, 10))
        self.label_item.setPos(4, 4)

    def _update_style(self):
        self.setPen(self.OVERFLOW_PEN if self._is_overflowing else self.NORMAL_PEN)


