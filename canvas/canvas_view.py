"""
CanvasView: het canvas-widget van vdp4free - toont de PDF-achtergrond en
alle geplaatste vakken, en bevat de logica voor records/fit-all/undo-
snapshots/laagvolgorde die alle vaktypes samenbrengt.
"""

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
)

from canvas.text_box import PlaceholderTextBox
from canvas.image_box import PlaceholderImageBox
from canvas.barcode_box import PlaceholderBarcodeBox
from canvas.shape_box import ShapeMaskBox


class CanvasView(QGraphicsView):
    """
    Het canvas: toont de PDF-achtergrond (indien geladen) en de
    tekst-/afbeeldings-/barcodevakken die de gebruiker erop plaatst.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        # Placeholder-paginaformaat totdat er een PDF geladen is
        # (A4 staand, in punten: 595 x 842)
        self._scene.setSceneRect(0, 0, 595, 842)
        self.setScene(self._scene)
        self.setBackgroundBrush(Qt.GlobalColor.darkGray)
        self.setRenderHints(self.renderHints())

        self._pdf_document = None  # referentie vasthouden, anders garbage collected
        self._background_item = None
        self._page_point_size = None
        self._pdf_path: str | None = None
        self._all_records: list[dict] = []
        self._current_record: dict | None = None
        self._current_record_index: int | None = None
        self._asset_base_dir: str | None = None
        self._asset_mapping: dict = {}

        # Optionele callback die MainWindow hierop kan zetten, zodat vakken
        # (bv. bij het verwijderen van zichzelf) het objectenpaneel kunnen
        # laten verversen en de job als "gewijzigd" kunnen laten markeren,
        # zonder dat CanvasView zelf een directe afhankelijkheid van
        # MainWindow nodig heeft.
        self.on_change_callback = None
        # Zelfde principe, maar dan VOORDAT een wijziging wordt toegepast -
        # gebruikt door MainWindow om een undo-snapshot te nemen.
        self.on_before_change_callback = None

    def notify_changed(self):
        """Roept de (optionele) callback aan die MainWindow heeft geregistreerd."""
        if self.on_change_callback is not None:
            self.on_change_callback()

    def capture_undo_point(self):
        """
        Aan te roepen VOORDAT een vak gewijzigd wordt (verplaatst, resized,
        eigenschap aangepast, verwijderd, etc.) - geeft MainWindow de kans
        om de huidige staat op de undo-stack te zetten.
        """
        if self.on_before_change_callback is not None:
            self.on_before_change_callback()

    def get_snapshot(self) -> dict:
        """Legt de volledige staat van alle plaatsbare vakken vast (voor undo/redo)."""
        return {
            "text_boxes": self.serialize_text_boxes(),
            "image_boxes": self.serialize_image_boxes(),
            "barcode_boxes": self.serialize_barcode_boxes(),
            "shape_boxes": self.serialize_shape_boxes(),
        }

    def restore_snapshot(self, snapshot: dict):
        """Herbouwt alle vakken vanuit een eerder vastgelegde snapshot (undo/redo)."""
        for box in self.get_all_boxes() + self.get_shape_boxes():
            self._scene.removeItem(box)
        self.load_text_boxes(snapshot.get("text_boxes", []))
        self.load_image_boxes(snapshot.get("image_boxes", []))
        self.load_barcode_boxes(snapshot.get("barcode_boxes", []))
        self.load_shape_boxes(snapshot.get("shape_boxes", []))
        # Herberekent fit_all_records-groottes EN past meteen het huidige
        # record weer toe (roept intern apply_record aan).
        self.recompute_fit_all_records()

    def bring_to_front(self, item):
        """Zet `item` bovenop alle andere plaatsbare vakken (niet de achtergrond)."""
        others = self.get_all_boxes() + self.get_shape_boxes()
        max_z = max((b.zValue() for b in others), default=0)
        item.setZValue(max_z + 1)

    def send_to_back(self, item):
        """Zet `item` achter alle andere plaatsbare vakken (niet de achtergrond)."""
        others = self.get_all_boxes() + self.get_shape_boxes()
        min_z = min((b.zValue() for b in others), default=0)
        item.setZValue(min_z - 1)

    def load_pdf(self, path: str):
        """Laadt de eerste pagina van een PDF en toont die als achtergrond."""
        doc = QPdfDocument(self)
        doc.load(path)

        if doc.status() != QPdfDocument.Status.Ready:
            return False, "Kon de PDF niet laden (bestand corrupt of geen PDF)."

        if doc.pageCount() < 1:
            return False, "De PDF bevat geen pagina's."

        page_index = 0
        page_size = doc.pagePointSize(page_index)  # afmeting in PDF-punten

        # Render op hogere resolutie dan de puntgrootte voor een scherp beeld,
        # de weergave wordt daarna teruggeschaald naar de echte paginamaat.
        render_scale = 2
        render_size = QSize(
            int(page_size.width() * render_scale),
            int(page_size.height() * render_scale),
        )
        image = doc.render(page_index, render_size)
        pixmap = QPixmap.fromImage(image)

        # Oude achtergrond en scene-inhoud opruimen
        self._scene.clear()
        self._scene.setSceneRect(0, 0, page_size.width(), page_size.height())
        self._all_records = []
        self._current_record = None
        self._current_record_index = None

        bg_item = QGraphicsPixmapItem(pixmap)
        bg_item.setScale(1 / render_scale)
        bg_item.setZValue(-1000)  # altijd achterop
        bg_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self._scene.addItem(bg_item)

        self._pdf_document = doc
        self._background_item = bg_item
        self._page_point_size = page_size
        self._pdf_path = path

        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        return True, None

    def add_text_placeholder(self):
        """Voegt een nieuw, verplaatsbaar placeholder-tekstvak toe."""
        box = PlaceholderTextBox(x=40, y=40)
        box._canvas = self
        self._scene.addItem(box)
        return box

    def add_image_placeholder(self):
        """Voegt een nieuw, verplaatsbaar placeholder-afbeeldingsvak toe."""
        box = PlaceholderImageBox(x=40, y=40)
        box._canvas = self
        self._scene.addItem(box)
        return box

    def add_barcode_placeholder(self):
        """Voegt een nieuw, verplaatsbaar barcode/QR-vak toe."""
        box = PlaceholderBarcodeBox(x=40, y=40)
        box._canvas = self
        self._scene.addItem(box)
        return box

    def add_shape_placeholder(self):
        """Voegt een nieuw, verplaatsbaar maskeervlak toe."""
        box = ShapeMaskBox(x=40, y=40)
        box._canvas = self
        self._scene.addItem(box)
        return box

    def get_selected_text_box(self):
        """Geeft het geselecteerde tekstvak terug, of None als er geen is."""
        for item in self._scene.selectedItems():
            if isinstance(item, PlaceholderTextBox):
                return item
        return None

    def get_selected_placeholder(self):
        """Geeft het geselecteerde tekst-, afbeeldings- of barcodevak terug, of None."""
        for item in self._scene.selectedItems():
            if isinstance(item, (PlaceholderTextBox, PlaceholderImageBox, PlaceholderBarcodeBox)):
                return item
        return None

    def get_text_boxes(self):
        """Alle tekstvakken op het canvas."""
        return [item for item in self._scene.items() if isinstance(item, PlaceholderTextBox)]

    def get_image_boxes(self):
        """Alle afbeeldingsvakken op het canvas."""
        return [item for item in self._scene.items() if isinstance(item, PlaceholderImageBox)]

    def get_barcode_boxes(self):
        """Alle barcode/QR-vakken op het canvas."""
        return [item for item in self._scene.items() if isinstance(item, PlaceholderBarcodeBox)]

    def get_shape_boxes(self):
        """Alle maskeervlakken op het canvas."""
        return [item for item in self._scene.items() if isinstance(item, ShapeMaskBox)]

    def get_all_boxes(self):
        """Alle tekst-, afbeeldings- en barcodevakken samen, voor generieke bewerkingen."""
        return self.get_text_boxes() + self.get_image_boxes() + self.get_barcode_boxes()

    def flag_missing_columns(self, available_columns: set[str]):
        """
        Zet een duidelijke, structurele waarschuwing op elk vak dat
        gekoppeld is aan een kolomnaam die niet in `available_columns`
        voorkomt - bv. na het (opnieuw) laden van een bestand met net
        iets andere kolomnamen. Dit overschrijft bewust wat apply_record()
        net heeft getoond, want dit is een ander soort probleem dan een
        simpel leeg veld voor één record: het geldt voor de HELE dataset.
        Nummering-vakken (value_source == "sequence") zijn niet
        kolom-gebonden en worden overgeslagen.
        """
        for box in self.get_all_boxes():
            field_name = getattr(box, "field_name", None)
            if not field_name:
                continue
            if isinstance(box, PlaceholderTextBox) and box.value_source != "field":
                continue
            if field_name not in available_columns:
                box.mark_missing_column()

    def set_asset_base_dir(self, path: str | None):
        """
        Stelt de map in waarin bestandsnamen uit een 'afbeelding'-kolom
        gezocht worden als het geen absoluut, bestaand pad is EN er geen
        (bij het openen van een .vdp4-package meegeleverde) exacte
        asset-mapping is. Normaal gesproken de map van de geladen CSV/Excel.
        """
        self._asset_base_dir = path

    def set_asset_mapping(self, mapping: dict | None):
        """
        Stelt een EXACTE koppeling in: {waarde_zoals_in_de_data: pad_op_schijf}.
        Wordt gebruikt na het openen van een .vdp4-package met gebundelde
        assets (zie project/package.py) - dat geeft een ondubbelzinnige
        koppeling, ongeacht hoe de oorspronkelijke bestandsnaam/submap
        eruitzag (lost het probleem op dat "customerA/foto.jpg" en
        "customerB/foto.jpg" elkaar zouden kunnen overschrijven bij een
        naam-gebaseerde aanpak).
        """
        self._asset_mapping = dict(mapping) if mapping else {}

    def resolve_asset_path(self, filename: str):
        """
        Zoekt het werkelijke bestandspad bij een waarde uit de data:
        1. Staat de waarde EXACT in de asset-mapping (van een geopend
           .vdp4-package): gebruik dat pad - dit heeft voorrang, want het
           is de meest betrouwbare, ondubbelzinnige bron.
        2. Als de waarde zelf een bestaand (absoluut) pad is: gebruik dat.
        3. Anders: probeer het te vinden in de asset-basismap.
        4. Anders: probeer het relatief aan de huidige werkmap.
        Geeft None terug als niets gevonden wordt.
        """
        if filename in self._asset_mapping:
            mapped = self._asset_mapping[filename]
            if Path(mapped).exists():
                return mapped

        direct = Path(filename)
        if direct.is_absolute() and direct.exists():
            return str(direct)

        if self._asset_base_dir:
            candidate = Path(self._asset_base_dir) / filename
            if candidate.exists():
                return str(candidate)

        if direct.exists():
            return str(direct)

        return None

    def apply_record(self, record: dict | None, record_index: int | None = None):
        """
        Toont voor elk vak de juiste weergave voor het huidige record:
        - tekstvakken met value_source == "sequence" krijgen hun
          automatisch gegenereerde nummer op basis van `record_index`
        - alle andere gekoppelde vakken (tekst/afbeelding/barcode) tonen
          de waarde uit `record` voor hun gekoppelde kolom
        - niet-gekoppelde vakken, of als record None is: sjabloonweergave
        """
        self._current_record = record
        self._current_record_index = record_index
        for box in self.get_all_boxes():
            if isinstance(box, PlaceholderTextBox) and box.value_source == "sequence":
                if record_index is not None:
                    box.show_sequence_value(record_index)
                else:
                    box.show_placeholder()
                continue
            if record is not None and box.field_name and box.field_name in record:
                box.show_value(record[box.field_name])
            else:
                box.show_placeholder()

    def get_current_record(self):
        return self._current_record

    def get_current_record_index(self):
        return self._current_record_index

    def set_records(self, records: list[dict]):
        """
        Stelt de volledige recordset in (voor fit_all_records-berekening)
        en herberekent meteen de lettergroottes van vakken die in die
        modus staan.
        """
        self._all_records = records or []
        self.recompute_fit_all_records()

    def recompute_fit_all_records(self):
        """
        Herberekent voor elk tekstvak in fit_mode "fit_all_records" één
        vaste lettergrootte: voor kolom-gekoppelde vakken op basis van de
        langste waarde in de dataset, voor nummering-vakken op basis van
        alle nummers die daadwerkelijk gegenereerd zouden worden over de
        volledige recordset.
        """
        n = len(self._all_records)
        for box in self.get_text_boxes():
            if box.fit_mode != "fit_all_records":
                continue
            if box.value_source == "sequence":
                if n:
                    values = [
                        box._format_sequence_value(i // max(box.seq_repeat, 1)) for i in range(n)
                    ]
                    box.fit_all(values)
            elif box.field_name and self._all_records:
                values = [str(r.get(box.field_name, "")) for r in self._all_records]
                box.fit_all(values)
        # Weergave meteen bijwerken met de nieuw berekende lettergroottes
        self.apply_record(self._current_record, self._current_record_index)

    def get_template_pdf_path(self):
        return self._pdf_path

    def serialize_text_boxes(self):
        """Legt id, laagvolgorde, positie, grootte, veldkoppeling, fit- en nummeringsinstellingen van elk tekstvak vast."""
        boxes = []
        for box in self.get_text_boxes():
            boxes.append(
                {
                    "id": box.element_id,
                    "z": box.zValue(),
                    "x": box.pos().x(),
                    "y": box.pos().y(),
                    "width": box.rect().width(),
                    "height": box.rect().height(),
                    "field_name": box.field_name,
                    "raw_text": box.text_item.toPlainText() if not box.field_name else None,
                    "font_family": box.font_family,
                    "font_bold": box.font_bold,
                    "font_italic": box.font_italic,
                    "base_font_size": box.base_font_size,
                    "min_font_size": box.min_font_size,
                    "fit_mode": box.fit_mode,
                    "value_source": box.value_source,
                    "seq_start": box.seq_start,
                    "seq_step": box.seq_step,
                    "seq_repeat": box.seq_repeat,
                    "seq_pad_length": box.seq_pad_length,
                    "seq_prefix": box.seq_prefix,
                    "seq_suffix": box.seq_suffix,
                }
            )
        return boxes

    def load_text_boxes(self, boxes_data: list[dict]):
        """Herbouwt tekstvakken vanuit opgeslagen jobdata (zie serialize_text_boxes)."""
        for data in boxes_data:
            text = data.get("raw_text") or "{{veld}}"
            box = PlaceholderTextBox(
                x=data.get("x", 20),
                y=data.get("y", 20),
                width=data.get("width", 160),
                height=data.get("height", 30),
                text=text,
                font_family=data.get("font_family", "Arial"),
                base_font_size=data.get("base_font_size", 12),
                min_font_size=data.get("min_font_size", 6),
                fit_mode=data.get("fit_mode", "shrink_to_fit"),
                element_id=data.get("id"),
            )
            box.setZValue(data.get("z", 0))
            box.font_bold = data.get("font_bold", False)
            box.font_italic = data.get("font_italic", False)
            box._canvas = self
            field_name = data.get("field_name")
            if field_name:
                box.field_name = field_name  # rechtstreeks zetten, geen recompute nu al
            box.value_source = data.get("value_source", "field")
            box.seq_start = data.get("seq_start", 1)
            box.seq_step = data.get("seq_step", 1)
            box.seq_repeat = data.get("seq_repeat", 1)
            box.seq_pad_length = data.get("seq_pad_length", 1)
            box.seq_prefix = data.get("seq_prefix", "")
            box.seq_suffix = data.get("seq_suffix", "")
            self._scene.addItem(box)

    def serialize_image_boxes(self):
        """Legt id, laagvolgorde, positie, grootte, veldkoppeling en crop-vorm van elk afbeeldingsvak vast."""
        boxes = []
        for box in self.get_image_boxes():
            boxes.append(
                {
                    "id": box.element_id,
                    "z": box.zValue(),
                    "x": box.pos().x(),
                    "y": box.pos().y(),
                    "width": box.rect().width(),
                    "height": box.rect().height(),
                    "field_name": box.field_name,
                    "crop_shape": box.crop_shape,
                }
            )
        return boxes

    def load_image_boxes(self, boxes_data: list[dict]):
        """Herbouwt afbeeldingsvakken vanuit opgeslagen jobdata."""
        for data in boxes_data:
            box = PlaceholderImageBox(
                x=data.get("x", 20),
                y=data.get("y", 20),
                width=data.get("width", 140),
                height=data.get("height", 100),
                field_name=data.get("field_name"),
                element_id=data.get("id"),
            )
            box.setZValue(data.get("z", 0))
            box.crop_shape = data.get("crop_shape", "none")
            box._canvas = self
            self._scene.addItem(box)

    def serialize_barcode_boxes(self):
        """Legt id, laagvolgorde, positie, grootte, veldkoppeling en type van elk barcode/QR-vak vast."""
        boxes = []
        for box in self.get_barcode_boxes():
            boxes.append(
                {
                    "id": box.element_id,
                    "z": box.zValue(),
                    "x": box.pos().x(),
                    "y": box.pos().y(),
                    "width": box.rect().width(),
                    "height": box.rect().height(),
                    "field_name": box.field_name,
                    "barcode_type": box.barcode_type,
                }
            )
        return boxes

    def load_barcode_boxes(self, boxes_data: list[dict]):
        """Herbouwt barcode/QR-vakken vanuit opgeslagen jobdata."""
        for data in boxes_data:
            box = PlaceholderBarcodeBox(
                x=data.get("x", 20),
                y=data.get("y", 20),
                width=data.get("width", 100),
                height=data.get("height", 100),
                field_name=data.get("field_name"),
                barcode_type=data.get("barcode_type", "qr"),
                element_id=data.get("id"),
            )
            box.setZValue(data.get("z", 0))
            box._canvas = self
            self._scene.addItem(box)

    def serialize_shape_boxes(self):
        """Legt id, laagvolgorde, positie, grootte, kleur en randstijl van elk maskeervlak vast."""
        boxes = []
        for box in self.get_shape_boxes():
            boxes.append(
                {
                    "id": box.element_id,
                    "z": box.zValue(),
                    "x": box.pos().x(),
                    "y": box.pos().y(),
                    "width": box.rect().width(),
                    "height": box.rect().height(),
                    "color": box.color,
                    "border_style": box.border_style,
                }
            )
        return boxes

    def load_shape_boxes(self, boxes_data: list[dict]):
        """Herbouwt maskeervlakken vanuit opgeslagen jobdata."""
        for data in boxes_data:
            box = ShapeMaskBox(
                x=data.get("x", 20),
                y=data.get("y", 20),
                width=data.get("width", 120),
                height=data.get("height", 60),
                color=data.get("color", "#ffffff"),
                border_style=data.get("border_style", "dashed"),
                element_id=data.get("id"),
            )
            box.setZValue(data.get("z", 0))
            box._canvas = self
            self._scene.addItem(box)

    def reset(self):
        """Wist het canvas volledig (nieuwe/lege job)."""
        self._scene.clear()
        self._scene.setSceneRect(0, 0, 595, 842)
        self._pdf_document = None
        self._background_item = None
        self._page_point_size = None
        self._pdf_path = None
        self._all_records = []
        self._current_record = None
        self._current_record_index = None
        self._asset_base_dir = None
        self._asset_mapping = {}

