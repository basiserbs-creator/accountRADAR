"""
vdp4free - vensterskelet met PDF-import, plaatsbare vakken, kolom-mapping en .vdp4-package
================================================================================================

Zie APP_VERSION hieronder - dat nummer staat ook in de titelbalk van het
venster, zodat je altijd kunt zien welke versie van dit bestand je
daadwerkelijk draait (handig zodra er meerdere main.py's rondzwerven).

Nieuw in deze versie (build 12):
- Lettertype-keuze per tekstvak (rechtsklik -> "Lettertype instellen...",
  inclusief vet/cursief) via de systeem-lettertypekiezer - toont alleen
  fonts die echt op dit systeem geïnstalleerd staan.
- Maskeervlak: nieuw vaktype (werkbalkknop "Maskeervlak") - een effen
  gekleurd vlak (standaard wit) om een deel van de PDF-achtergrond af te
  dekken. Kleur instelbaar via rechtsklik.
- Afbeeldingsvak kan nu ook rond bijgesneden worden (rechtsklik -> "Vorm:
  Rond bijsnijden").
- "Verwijderen" toegevoegd aan het rechtsklikmenu van elk vaktype.

Eerder toegevoegd (build 11) - zes verbeteringen na kritische review:
- Bugfix: canvas-records blijven nu gesynchroniseerd na het opnieuw
  importeren van een PDF-sjabloon.
- CSV-delimiter (komma/puntkomma/tab) wordt automatisch herkend.
- Waarschuwing bij niet-opgeslagen wijzigingen (Nieuwe job/Openen/Afsluiten).
- Nog niet geïmplementeerde knoppen (Undo/Redo/Zoom/Preflight/Produceren)
  zijn zichtbaar uitgeschakeld i.p.v. een knop die niets doet.
- Lichte fontcontrole bij opstarten (waarschuwt als het standaard-
  lettertype niet echt geïnstalleerd is).
- Job opslaan is nu atomair (tmp-bestand + hernoemen).

Eerder toegevoegd, nog steeds relevant:
- Kolom-mapping bij afwijkende kolomnamen tussen sjabloon en databron.
- Nummering ("Generated Field") via rechtsklik op een tekstvak.
- Barcode/QR-vak gebruikt de gratis/open-source libraries `qrcode` en
  `python-barcode` (MIT-licentie). Eenmalig installeren in de venv:
      pip install qrcode python-barcode
- Het .vdp4-package bevat nog geen kopie van afbeeldingsbestanden zelf
  (alleen van de PDF en de CSV/Excel) - volledige assets-bundeling is
  een latere uitbreiding.

Starten:
    source .venv/bin/activate
    python main.py
"""

APP_VERSION = "build 12"

import csv
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

import barcode
import openpyxl
import qrcode
from barcode.writer import ImageWriter
from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFontDialog,
    QFormLayout,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


class ObjectsPanel(QWidget):
    """Linkerpaneel: lijst van objecten/layers op de huidige pagina."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Objecten</b>"))

        self.object_list = QListWidget()
        layout.addWidget(self.object_list)


class DataPanel(QWidget):
    """
    Rechterpaneel: laadt een echte CSV of Excel(.xlsx)-databron en toont
    de gevonden kolomnamen. De ingelezen records (lijst van dicts, één
    dict per rij) worden bewaard in self.records voor later gebruik
    (koppeling aan placeholders, recordnavigatie/preview).
    """

    # Wordt uitgezonden zodra data succesvol geladen is:
    # (bestandsnaam: str, kolomnamen: list[str], aantal_records: int)
    data_loaded = Signal(str, list, int)
    # Wordt uitgezonden als de gebruiker dubbelklikt op een kolomnaam
    column_double_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.records: list[dict] = []
        self.column_names: list[str] = []
        self.loaded_path: str | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Data</b>"))

        self.load_button = QPushButton("CSV/Excel laden...")
        self.load_button.clicked.connect(self.on_load_clicked)
        layout.addWidget(self.load_button)

        self.info_label = QLabel("Nog geen data geladen")
        layout.addWidget(self.info_label)

        self.column_table = QTableWidget(0, 1)
        self.column_table.setHorizontalHeaderLabels(["Kolomnaam"])
        self.column_table.horizontalHeader().setStretchLastSection(True)
        self.column_table.itemDoubleClicked.connect(self._on_column_double_clicked)
        layout.addWidget(self.column_table)

    # ------------------------------------------------------------------
    def on_load_clicked(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Data laden",
            "",
            "Data-bestanden (*.csv *.xlsx);;CSV-bestanden (*.csv);;Excel-bestanden (*.xlsx)",
        )
        if not path:
            return

        try:
            if path.lower().endswith(".csv"):
                columns, records = self._load_csv(path)
            elif path.lower().endswith(".xlsx"):
                columns, records = self._load_xlsx(path)
            else:
                QMessageBox.warning(
                    self, "Onbekend bestandstype", "Kies een .csv- of .xlsx-bestand."
                )
                return
        except Exception as exc:  # noqa: BLE001 - toon elke leesfout aan de gebruiker
            QMessageBox.critical(self, "Kon databestand niet lezen", str(exc))
            return

        if not columns:
            QMessageBox.warning(
                self, "Geen kolommen gevonden", "Het bestand lijkt geen headerrij te hebben."
            )
            return

        self.column_names = columns
        self.records = records
        self.loaded_path = path
        self._populate_table(columns)

        filename = Path(path).name
        self.info_label.setText(f"{filename} - {len(records)} record(en)")
        self.data_loaded.emit(filename, columns, len(records))

    # ------------------------------------------------------------------
    def load_from_path(self, path: str):
        """
        Laadt data vanaf een bekend pad zonder bestandskiezer - gebruikt
        bij het openen van een opgeslagen job. Geeft (succes, foutmelding)
        terug, net als canvas.load_pdf().
        """
        try:
            if path.lower().endswith(".csv"):
                columns, records = self._load_csv(path)
            elif path.lower().endswith(".xlsx"):
                columns, records = self._load_xlsx(path)
            else:
                return False, "Onbekend bestandstype (verwacht .csv of .xlsx)."
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)

        if not columns:
            return False, "Het bestand lijkt geen headerrij te hebben."

        self.column_names = columns
        self.records = records
        self.loaded_path = path
        self._populate_table(columns)

        filename = Path(path).name
        self.info_label.setText(f"{filename} - {len(records)} record(en)")
        self.data_loaded.emit(filename, columns, len(records))
        return True, None

    # ------------------------------------------------------------------
    def reset(self):
        self.records = []
        self.column_names = []
        self.loaded_path = None
        self.column_table.setRowCount(0)
        self.info_label.setText("Nog geen data geladen")

    # ------------------------------------------------------------------
    def _load_csv(self, path: str):
        with open(path, newline="", encoding="utf-8-sig") as f:
            sample = f.read(8192)
            f.seek(0)
            # Nederlandse Excel-exports gebruiken vaak puntkomma i.p.v. komma
            # als scheidingsteken - dit voorkomt dat zo'n bestand er "kapot"
            # uitziet (alles in één kolom) zonder duidelijke reden.
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
            except csv.Error:
                dialect = csv.excel  # standaard komma, als detectie niet lukt
            reader = csv.DictReader(f, dialect=dialect)
            columns = reader.fieldnames or []
            records = [dict(row) for row in reader]
        return list(columns), records

    def _load_xlsx(self, path: str):
        workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
        sheet = workbook.active

        rows_iter = sheet.iter_rows(values_only=True)
        try:
            header_row = next(rows_iter)
        except StopIteration:
            return [], []

        columns = [str(c) if c is not None else "" for c in header_row]
        records = []
        for row in rows_iter:
            if row is None or all(v is None for v in row):
                continue  # lege rij overslaan
            record = {columns[i]: row[i] for i in range(len(columns)) if i < len(row)}
            records.append(record)
        return columns, records

    # ------------------------------------------------------------------
    def _on_column_double_clicked(self, item):
        self.column_double_clicked.emit(item.text())

    # ------------------------------------------------------------------
    def _populate_table(self, columns: list[str]):
        self.column_table.setRowCount(len(columns))
        for row, name in enumerate(columns):
            self.column_table.setItem(row, 0, QTableWidgetItem(name))


class PlaceholderTextBox(QGraphicsRectItem):
    """
    Een verplaatsbaar EN VERGROOTBAAR tekstvak met placeholder-tekst
    (bv. {{Voornaam}}). Dubbelklikken activeert het handmatig bewerken
    van de tekst. Rechtsklikken opent een menu om de fit-modus en
    lettergroottes in te stellen. Slepen aan het blauwe hoekje rechts-
    onder past de afmeting van het vak aan.

    Een vak kan gekoppeld worden aan een kolomnaam (via set_field). Zodra
    dat gebeurd is, kan het vak wisselen tussen de placeholder-notatie
    ({{Voornaam}}) en een echte waarde uit een record ("Jan") - dat is de
    basis voor de recordnavigatie/live preview.

    FIT-MODI (drie stuks, zoals afgesproken - nooit stil afkappen):
    - "fixed": altijd de basislettergrootte, ongeacht of de tekst past
    - "shrink_to_fit": verkleint de lettergrootte (tot het ingestelde
      minimum) zodat de HUIDIGE tekst past
    - "fit_all_records": analyseert alle records van de gekoppelde kolom
      en kiest ÉÉN lettergrootte waarmee de langste waarde past - zodat
      niet elk record een andere fontgrootte krijgt

    Het passen wordt gecontroleerd op zowel BREEDTE als HOOGTE (een grote
    lettergrootte kan qua breedte net passen, maar toch boven/onder het
    vak uitsteken - dat telt ook als overflow).

    Als de tekst ook bij de minimum-lettergrootte niet past, wordt de
    tekst NOOIT afgekapt - in plaats daarvan krijgt het vak een rode
    rand als visuele waarschuwing (_is_overflowing).
    """

    NORMAL_PEN = QPen(QColor(30, 100, 220), 1)
    OVERFLOW_PEN = QPen(QColor(220, 30, 30), 2)
    RESIZE_HANDLE_SIZE = 10
    MIN_BOX_WIDTH = 30
    MIN_BOX_HEIGHT = 16

    def __init__(
        self,
        x=20,
        y=20,
        width=160,
        height=30,
        text="{{veld}}",
        font_family="Arial",
        base_font_size=12,
        min_font_size=6,
        fit_mode="shrink_to_fit",
    ):
        super().__init__(0, 0, width, height)
        self.setPos(x, y)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setBrush(QBrush(QColor(255, 255, 255, 210)))
        self.setPen(self.NORMAL_PEN)

        self.field_name: str | None = None  # gekoppelde kolomnaam, indien aanwezig
        self.font_family = font_family
        self.font_bold = False
        self.font_italic = False
        self.base_font_size = base_font_size
        self.min_font_size = min_font_size
        self.fit_mode = fit_mode  # "fixed" | "shrink_to_fit" | "fit_all_records"
        self._is_overflowing = False
        self._canvas = None  # wordt gezet door CanvasView bij aanmaken
        self._resizing = False
        self._resize_start_scene_pos = None
        self._resize_start_rect = None

        # Nummering ("Generated Field") - een tekstvak toont OFTEWEL de
        # waarde van een gekoppelde kolom (value_source == "field") OFTEWEL
        # een automatisch gegenereerd volgnummer (value_source == "sequence").
        # Zie set_field() / _configure_sequence() voor hoe je hiertussen wisselt.
        self.value_source = "field"  # "field" | "sequence"
        self.seq_start = 1
        self.seq_step = 1
        self.seq_repeat = 1  # elk nummer x keer herhalen (bv. 1,1,2,2,...)
        self.seq_pad_length = 1  # voorloopnullen: minimale lengte van het getal
        self.seq_prefix = ""
        self.seq_suffix = ""

        self.text_item = QGraphicsTextItem(text, self)
        self.text_item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.text_item.setPos(4, 4)
        self.text_item.setFont(self._make_font(self.base_font_size))
        self.text_item.document().contentsChanged.connect(self._on_text_content_changed)

    def _make_font(self, size: int) -> QFont:
        """
        Bouwt een QFont met de huidige family/vet/cursief-instellingen op
        de gegeven grootte. Centraal gebruikt zodat lettertype-eigenschappen
        overal consistent zijn - ook in de fit-berekeningen (bold/italic
        tekst is immers breder dan gewone tekst).
        """
        font = QFont(self.font_family, size)
        font.setBold(self.font_bold)
        font.setItalic(self.font_italic)
        return font

    def mouseDoubleClickEvent(self, event):
        if self._is_in_resize_handle(event.pos()):
            return  # dubbelklik op het hoekje mag geen tekstbewerking starten
        self.text_item.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextEditorInteraction
        )
        self.text_item.setFocus()
        super().mouseDoubleClickEvent(event)

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
            self._notify_settings_changed()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        r = self.rect()
        handle = QRectF(
            r.width() - self.RESIZE_HANDLE_SIZE,
            r.height() - self.RESIZE_HANDLE_SIZE,
            self.RESIZE_HANDLE_SIZE,
            self.RESIZE_HANDLE_SIZE,
        )
        painter.fillRect(handle, QColor(30, 100, 220))

    def contextMenuEvent(self, event):
        menu = QMenu()

        field_source_action = menu.addAction("Bron: Kolom (data)")
        field_source_action.setCheckable(True)
        field_source_action.setChecked(self.value_source == "field")

        seq_configure_action = menu.addAction("Nummering instellen...")

        menu.addSeparator()
        fixed_action = menu.addAction("Modus: Vast")
        fixed_action.setCheckable(True)
        fixed_action.setChecked(self.fit_mode == "fixed")

        shrink_action = menu.addAction("Modus: Shrink-to-fit")
        shrink_action.setCheckable(True)
        shrink_action.setChecked(self.fit_mode == "shrink_to_fit")

        fitall_action = menu.addAction("Modus: Fit-all-records")
        fitall_action.setCheckable(True)
        fitall_action.setChecked(self.fit_mode == "fit_all_records")

        menu.addSeparator()
        size_action = menu.addAction(f"Basislettergrootte instellen... ({self.base_font_size} pt)")
        min_action = menu.addAction(f"Minimum lettergrootte instellen... ({self.min_font_size} pt)")
        font_action = menu.addAction(f"Lettertype instellen... ({self.font_family})")

        menu.addSeparator()
        delete_action = menu.addAction("Verwijderen")

        chosen = menu.exec(event.screenPos())

        if chosen == field_source_action:
            self.value_source = "field"
            self._refresh_display_from_canvas()
        elif chosen == seq_configure_action:
            self._configure_sequence()
        elif chosen == fixed_action:
            self.set_fit_mode("fixed")
        elif chosen == shrink_action:
            self.set_fit_mode("shrink_to_fit")
        elif chosen == fitall_action:
            self.set_fit_mode("fit_all_records")
        elif chosen == size_action:
            value, ok = self._ask_int("Basislettergrootte", "Punten:", self.base_font_size, 4, 200)
            if ok:
                self.base_font_size = value
                self._notify_settings_changed()
        elif chosen == min_action:
            value, ok = self._ask_int("Minimum lettergrootte", "Punten:", self.min_font_size, 2, 200)
            if ok:
                self.min_font_size = value
                self._notify_settings_changed()
        elif chosen == font_action:
            self._configure_font()
        elif chosen == delete_action:
            self._delete_self()

    def _configure_font(self):
        """
        Opent de systeem-lettertypekiezer (toont alleen echt op dit
        systeem geïnstalleerde fonts - dus geen risico op een niet-
        bestaand lettertype kiezen). Neemt ook meteen vet/cursief en de
        gekozen grootte over als basislettergrootte.
        """
        initial = self._make_font(self.base_font_size)
        chosen_font, ok = QFontDialog.getFont(initial, None, "Lettertype kiezen")
        if not ok:
            return
        self.font_family = chosen_font.family()
        self.font_bold = chosen_font.bold()
        self.font_italic = chosen_font.italic()
        if chosen_font.pointSize() > 0:
            self.base_font_size = chosen_font.pointSize()
        self._notify_settings_changed()

    def _delete_self(self):
        """Verwijdert dit vak van het canvas en meldt de wijziging aan MainWindow."""
        scene = self.scene()
        if scene is not None:
            scene.removeItem(self)
        if self._canvas is not None:
            self._canvas.notify_changed()

    @staticmethod
    def _ask_int(title: str, label: str, current: int, minv: int, maxv: int):
        """
        Zelfde als QInputDialog.getInt(), maar met een minimumbreedte -
        anders wordt op macOS de titelbalktekst soms afgekapt.
        """
        dialog = QInputDialog()
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setInputMode(QInputDialog.InputMode.IntInput)
        dialog.setIntRange(minv, maxv)
        dialog.setIntValue(current)
        dialog.resize(340, dialog.sizeHint().height())
        ok = dialog.exec() == QInputDialog.DialogCode.Accepted
        return dialog.intValue(), ok

    @staticmethod
    def _ask_text(title: str, label: str, current: str):
        """Zelfde als QInputDialog.getText(), maar met een minimumbreedte."""
        dialog = QInputDialog()
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setInputMode(QInputDialog.InputMode.TextInput)
        dialog.setTextValue(current)
        dialog.resize(340, dialog.sizeHint().height())
        ok = dialog.exec() == QInputDialog.DialogCode.Accepted
        return dialog.textValue(), ok

    def _configure_sequence(self):
        """
        Vraagt via een reeks dialoogvensters de nummering-instellingen op
        (startwaarde, stapgrootte, herhaling, voorloopnullen, prefix,
        suffix). Annuleren op elk moment laat de bestaande instellingen
        ongewijzigd. Bij succesvol voltooien schakelt het vak automatisch
        naar value_source == "sequence".
        """
        start, ok = self._ask_int(
            "Nummering", "Startwaarde:", self.seq_start, -999999, 999999
        )
        if not ok:
            return
        step, ok = self._ask_int(
            "Nummering", "Stapgrootte:", self.seq_step, -999999, 999999
        )
        if not ok:
            return
        repeat, ok = self._ask_int(
            "Nummering", "Elk nummer herhalen (x keer):", self.seq_repeat, 1, 999
        )
        if not ok:
            return
        pad, ok = self._ask_int(
            "Nummering", "Minimale lengte (opgevuld met nullen):", self.seq_pad_length, 1, 20
        )
        if not ok:
            return
        prefix, ok = self._ask_text("Nummering", "Prefix (optioneel):", self.seq_prefix)
        if not ok:
            return
        suffix, ok = self._ask_text("Nummering", "Suffix (optioneel):", self.seq_suffix)
        if not ok:
            return

        self.seq_start = start
        self.seq_step = step
        self.seq_repeat = repeat
        self.seq_pad_length = pad
        self.seq_prefix = prefix
        self.seq_suffix = suffix
        self.value_source = "sequence"
        self._refresh_display_from_canvas()

    def _refresh_display_from_canvas(self):
        """
        Ververst de weergave na een bronwijziging (kolom <-> nummering).
        Bij fit_all_records moet de hele dataset opnieuw doorgerekend
        worden; anders volstaat het opnieuw tonen van het huidige record.
        """
        if self._canvas is None:
            self.show_placeholder()
            return
        if self.fit_mode == "fit_all_records":
            self._canvas.recompute_fit_all_records()
        else:
            self._canvas.apply_record(
                self._canvas.get_current_record(), self._canvas.get_current_record_index()
            )

    # ------------------------------------------------------------------
    def set_field(self, field_name: str):
        """Koppelt dit vak aan een kolomnaam (schakelt de bron terug naar 'field')."""
        self.field_name = field_name
        self.value_source = "field"
        self._notify_settings_changed()

    def set_fit_mode(self, mode: str):
        self.fit_mode = mode
        self._notify_settings_changed()

    def _notify_settings_changed(self):
        """
        Na een wijziging die de weergave beinvloedt: bij fit_all_records
        moet de hele dataset opnieuw geanalyseerd worden (dat kan alleen
        het canvas, want dat kent de records). In alle andere gevallen
        volstaat het herberekenen op basis van de huidige, al zichtbare
        tekst. Als set_field() net een nieuwe kolom koppelde, wordt de
        weergave daarna sowieso overschreven door apply_record() vanuit
        MainWindow - dit hoeft dus geen rekening te houden met welke
        tekst er precies staat.
        """
        if self.fit_mode == "fit_all_records" and self._canvas is not None:
            self._canvas.recompute_fit_all_records()
        else:
            self._refit_current_text()

    def _format_sequence_value(self, logical_index: int) -> str:
        """Formatteert één nummer volgens de ingestelde stap/voorloopnullen/prefix/suffix."""
        number = self.seq_start + logical_index * self.seq_step
        return f"{self.seq_prefix}{str(number).zfill(self.seq_pad_length)}{self.seq_suffix}"

    def show_sequence_value(self, record_index: int):
        """
        Toont het automatisch gegenereerde nummer voor de gegeven
        (0-based) recordpositie. Meerdere opeenvolgende records kunnen
        hetzelfde nummer krijgen via seq_repeat (bv. 1,1,2,2,...).
        """
        logical_index = record_index // max(self.seq_repeat, 1)
        text = self._format_sequence_value(logical_index)
        self.text_item.setPlainText(text)
        if self.fit_mode != "fit_all_records":
            self._refit_current_text()
        else:
            self._update_overflow_style()

    def show_placeholder(self):
        """
        Toont de sjabloonweergave: bij value_source == "sequence" een
        voorbeeldnummer (op basis van de startwaarde), anders de
        {{kolomnaam}}-notatie. Voor "fixed" en "shrink_to_fit" gaat dit
        terug naar de basislettergrootte. Voor "fit_all_records" blijft
        de eerder berekende, dataset-brede lettergrootte staan - anders
        zou een tussentijdse aanroep zonder actief record (bv. vlak na
        het laden van data) de zojuist berekende grootte weer
        overschrijven.
        """
        if self.value_source == "sequence":
            self.text_item.setPlainText("🔢 " + self._format_sequence_value(0))
        elif self.field_name:
            self.text_item.setPlainText("{{" + self.field_name + "}}")
        if self.fit_mode != "fit_all_records":
            self.text_item.setFont(self._make_font(self.base_font_size))
            self._is_overflowing = False
        self._update_overflow_style()


    def show_value(self, value):
        """Toont een echte waarde uit een record (previewweergave)."""
        text = "" if value is None else str(value)
        self.text_item.setPlainText(text)
        if self.fit_mode != "fit_all_records":
            self._refit_current_text()
        else:
            # Lettergrootte staat al vast via fit_all(); alleen stijl bijwerken
            self._update_overflow_style()

    def mark_missing_column(self):
        """
        Structurele waarschuwing: dit vak is gekoppeld aan een kolomnaam
        die niet (meer) bestaat in de geladen dataset - bv. na het laden
        van een ander bestand met net iets andere kolomnamen. Anders dan
        een gewone lege waarde voor één record: dit geldt voor de HELE
        dataset en moet opvallen (mapping-scherm lost dit meestal op).
        """
        self.text_item.setPlainText(f"⚠ kolom '{self.field_name}' niet gevonden")
        if self.fit_mode != "fit_all_records":
            self.text_item.setFont(self._make_font(self.base_font_size))
        self._is_overflowing = True
        self._update_overflow_style()

    def fit_all(self, values: list[str]):
        """
        Bepaalt ÉÉN lettergrootte waarmee alle gegeven waarden passen
        (gebruikt voor fit_mode == "fit_all_records"). Wordt aangeroepen
        door CanvasView.recompute_fit_all_records().
        """
        font_size, overflow = self._compute_fitting_font_size(values or [""])
        self.base_font_size_effective = font_size  # informatief, voor eventuele UI later
        self.text_item.setFont(self._make_font(font_size))
        self._is_overflowing = overflow
        self._update_overflow_style()

    # ------------------------------------------------------------------
    def _refit_current_text(self):
        """Pas de lettergrootte aan zodat de HUIDIGE tekst past (fixed/shrink_to_fit)."""
        text = self.text_item.toPlainText()
        if self.fit_mode == "fixed":
            font = self._make_font(self.base_font_size)
            metrics = QFontMetricsF(font)
            fits_width = metrics.horizontalAdvance(text) <= self._available_width()
            fits_height = metrics.height() <= self._available_height()
            self._is_overflowing = not (fits_width and fits_height)
            self.text_item.setFont(font)
        else:  # shrink_to_fit
            font_size, overflow = self._compute_fitting_font_size([text])
            self.text_item.setFont(self._make_font(font_size))
            self._is_overflowing = overflow
        self._update_overflow_style()

    def _compute_fitting_font_size(self, texts: list[str]):
        """
        Zoekt de grootste lettergrootte (tussen min en basis) waarbij ALLE
        gegeven teksten passen, zowel in BREEDTE als in HOOGTE. Geeft
        (lettergrootte, overflow) terug - overflow is True als zelfs de
        minimum-grootte niet voldoet.
        """
        available_width = self._available_width()
        available_height = self._available_height()
        font_size = self.base_font_size
        while font_size > self.min_font_size:
            font = self._make_font(font_size)
            metrics = QFontMetricsF(font)
            fits_width = all(metrics.horizontalAdvance(t) <= available_width for t in texts)
            fits_height = metrics.height() <= available_height
            if fits_width and fits_height:
                return font_size, False
            font_size -= 1

        # Laatste check exact op de minimum-grootte
        font = self._make_font(self.min_font_size)
        metrics = QFontMetricsF(font)
        fits_width = all(metrics.horizontalAdvance(t) <= available_width for t in texts)
        fits_height = metrics.height() <= available_height
        overflow = not (fits_width and fits_height)
        return self.min_font_size, overflow

    def _available_width(self):
        return max(self.rect().width() - 8, 1)  # 8 = padding (4px links + rechts)

    def _available_height(self):
        return max(self.rect().height() - 8, 1)  # 8 = padding (4px boven + onder)

    def _update_overflow_style(self):
        self.setPen(self.OVERFLOW_PEN if self._is_overflowing else self.NORMAL_PEN)

    def _on_text_content_changed(self):
        """Reageert op handmatige tekstbewerking (dubbelklik + typen)."""
        if self.fit_mode != "fit_all_records":
            self._refit_current_text()


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

    def __init__(self, x=20, y=20, width=140, height=100, field_name=None):
        super().__init__(0, 0, width, height)
        self.setPos(x, y)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setBrush(QBrush(QColor(255, 250, 235, 210)))
        self.setPen(self.NORMAL_PEN)

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

        self.show_placeholder()

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

    def mousePressEvent(self, event):
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
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        r = self.rect()
        handle = QRectF(
            r.width() - self.RESIZE_HANDLE_SIZE,
            r.height() - self.RESIZE_HANDLE_SIZE,
            self.RESIZE_HANDLE_SIZE,
            self.RESIZE_HANDLE_SIZE,
        )
        painter.fillRect(handle, QColor(180, 120, 30))

    def contextMenuEvent(self, event):
        menu = QMenu()

        none_action = menu.addAction("Vorm: Rechthoek (geen bijsnijden)")
        none_action.setCheckable(True)
        none_action.setChecked(self.crop_shape == "none")

        circle_action = menu.addAction("Vorm: Rond bijsnijden")
        circle_action.setCheckable(True)
        circle_action.setChecked(self.crop_shape == "circle")

        menu.addSeparator()
        delete_action = menu.addAction("Verwijderen")

        chosen = menu.exec(event.screenPos())
        if chosen == none_action:
            self.crop_shape = "none"
            self._rescale_pixmap()
        elif chosen == circle_action:
            self.crop_shape = "circle"
            self._rescale_pixmap()
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

    def __init__(self, x=20, y=20, width=100, height=100, field_name=None, barcode_type="qr"):
        super().__init__(0, 0, width, height)
        self.setPos(x, y)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setBrush(QBrush(QColor(245, 245, 245, 210)))
        self.setPen(self.NORMAL_PEN)

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

        self.show_placeholder()

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
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        r = self.rect()
        handle = QRectF(
            r.width() - self.RESIZE_HANDLE_SIZE,
            r.height() - self.RESIZE_HANDLE_SIZE,
            self.RESIZE_HANDLE_SIZE,
            self.RESIZE_HANDLE_SIZE,
        )
        painter.fillRect(handle, QColor(90, 90, 90))

    def contextMenuEvent(self, event):
        menu = QMenu()
        qr_action = menu.addAction("Type: QR-code")
        qr_action.setCheckable(True)
        qr_action.setChecked(self.barcode_type == "qr")

        code128_action = menu.addAction("Type: Barcode (Code128)")
        code128_action.setCheckable(True)
        code128_action.setChecked(self.barcode_type == "code128")

        menu.addSeparator()
        delete_action = menu.addAction("Verwijderen")

        chosen = menu.exec(event.screenPos())
        if chosen == qr_action:
            self.barcode_type = "qr"
            self._regenerate_from_current_value()
        elif chosen == code128_action:
            self.barcode_type = "code128"
            self._regenerate_from_current_value()
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


class ShapeMaskBox(QGraphicsRectItem):
    """
    Een verplaatsbaar EN vergrootbaar maskeervlak: een ondoorzichtige,
    effen gekleurde rechthoek die je over de PDF-achtergrond legt om een
    deel ervan af te dekken (bv. een voorbedrukt logo of oud adresvak).

    Geen datakoppeling - dit is een puur statisch opmaakelement, geen
    placeholder. Staat altijd boven de achtergrond (die een vaste lage
    z-waarde heeft), dus dekt automatisch af wat eronder ligt.
    """

    SELECTED_BORDER_PEN = QPen(QColor(90, 90, 90), 1, Qt.PenStyle.DashLine)
    RESIZE_HANDLE_SIZE = 10
    MIN_BOX_WIDTH = 10
    MIN_BOX_HEIGHT = 10

    def __init__(self, x=20, y=20, width=120, height=60, color="#ffffff"):
        super().__init__(0, 0, width, height)
        self.setPos(x, y)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.color = color
        self.setBrush(QBrush(QColor(color)))
        self.setPen(self.SELECTED_BORDER_PEN)

        self._canvas = None  # wordt gezet door CanvasView bij aanmaken
        self._resizing = False
        self._resize_start_scene_pos = None
        self._resize_start_rect = None

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
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        # De stippellijnrand is bewust altijd zichtbaar (ook als het vak
        # niet geselecteerd is) - anders is een wit maskeervlak op een
        # witte achtergrond straks onzichtbaar om te selecteren/verslepen.
        r = self.rect()
        handle = QRectF(
            r.width() - self.RESIZE_HANDLE_SIZE,
            r.height() - self.RESIZE_HANDLE_SIZE,
            self.RESIZE_HANDLE_SIZE,
            self.RESIZE_HANDLE_SIZE,
        )
        painter.fillRect(handle, QColor(90, 90, 90))

    def contextMenuEvent(self, event):
        menu = QMenu()
        color_action = menu.addAction("Kleur instellen...")
        menu.addSeparator()
        delete_action = menu.addAction("Verwijderen")

        chosen = menu.exec(event.screenPos())
        if chosen == color_action:
            chosen_color = QColorDialog.getColor(QColor(self.color), None, "Maskerkleur kiezen")
            if chosen_color.isValid():
                self.color = chosen_color.name()
                self.setBrush(QBrush(QColor(self.color)))
        elif chosen == delete_action:
            scene = self.scene()
            if scene is not None:
                scene.removeItem(self)
            if self._canvas is not None:
                self._canvas.notify_changed()


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

        # Optionele callback die MainWindow hierop kan zetten, zodat vakken
        # (bv. bij het verwijderen van zichzelf) het objectenpaneel kunnen
        # laten verversen en de job als "gewijzigd" kunnen laten markeren,
        # zonder dat CanvasView zelf een directe afhankelijkheid van
        # MainWindow nodig heeft.
        self.on_change_callback = None

    def notify_changed(self):
        """Roept de (optionele) callback aan die MainWindow heeft geregistreerd."""
        if self.on_change_callback is not None:
            self.on_change_callback()

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
        gezocht worden als het geen absoluut, bestaand pad is. Normaal
        gesproken de map van de geladen CSV/Excel.
        """
        self._asset_base_dir = path

    def resolve_asset_path(self, filename: str):
        """
        Zoekt het werkelijke bestandspad bij een waarde uit de data:
        1. Als de waarde zelf een bestaand (absoluut) pad is: gebruik dat.
        2. Anders: probeer het te vinden in de asset-basismap.
        3. Anders: probeer het relatief aan de huidige werkmap.
        Geeft None terug als niets gevonden wordt.
        """
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
        """Legt positie, grootte, veldkoppeling, fit- en nummeringsinstellingen van elk tekstvak vast."""
        boxes = []
        for box in self.get_text_boxes():
            boxes.append(
                {
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
            )
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
        """Legt positie, grootte, veldkoppeling en crop-vorm van elk afbeeldingsvak vast."""
        boxes = []
        for box in self.get_image_boxes():
            boxes.append(
                {
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
            )
            box.crop_shape = data.get("crop_shape", "none")
            box._canvas = self
            self._scene.addItem(box)

    def serialize_barcode_boxes(self):
        """Legt positie, grootte, veldkoppeling en type van elk barcode/QR-vak vast."""
        boxes = []
        for box in self.get_barcode_boxes():
            boxes.append(
                {
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
            )
            box._canvas = self
            self._scene.addItem(box)

    def serialize_shape_boxes(self):
        """Legt positie, grootte en kleur van elk maskeervlak vast."""
        boxes = []
        for box in self.get_shape_boxes():
            boxes.append(
                {
                    "x": box.pos().x(),
                    "y": box.pos().y(),
                    "width": box.rect().width(),
                    "height": box.rect().height(),
                    "color": box.color,
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
            )
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


class MappingDialog(QDialog):
    """
    Verschijnt automatisch na het laden van data zodra één of meer vakken
    gekoppeld zijn aan een kolomnaam die niet in het nieuwe bestand
    voorkomt (bv. sjabloon eerder gemaakt met "Voornaam", nieuwe klant
    levert een bestand aan met "Naam1"). Laat de gebruiker per ontbrekend
    veld een bestaande kolom kiezen, of "(geen koppeling)" om het zo te
    laten (het vak toont dan een duidelijke waarschuwing).
    """

    def __init__(self, missing_fields: list[str], available_columns: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kolommen koppelen")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Deze databron heeft niet alle kolommen die je sjabloon verwacht.\n"
            "Koppel hieronder elk ontbrekend veld aan de juiste kolom uit dit "
            "bestand, of laat het ongekoppeld."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self._combos: dict[str, QComboBox] = {}
        form = QFormLayout()
        for field in missing_fields:
            combo = QComboBox()
            combo.addItem("(geen koppeling)", None)
            for col in available_columns:
                combo.addItem(col, col)
            # Alvast een voor de hand liggende suggestie selecteren
            # (zelfde naam, hoofdletterongevoelig) als die bestaat.
            for i in range(combo.count()):
                item_data = combo.itemData(i)
                if item_data and item_data.lower() == field.lower():
                    combo.setCurrentIndex(i)
                    break
            form.addRow(f"{field}:", combo)
            self._combos[field] = combo
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_mapping(self) -> dict:
        """Geeft {oude_kolomnaam: nieuwe_kolomnaam_of_None} terug."""
        return {field: combo.currentData() for field, combo in self._combos.items()}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"vdp4free (werknaam) - PDF-canvas - {APP_VERSION}")
        self.resize(1200, 800)

        self.records: list[dict] = []
        self.current_index: int = -1
        self._dirty = False  # niet-opgeslagen wijzigingen? zie mark_dirty()

        self._build_central_widget()
        self._build_menubar()
        self._build_toolbar()
        self._build_docks()
        self._build_statusbar()

    # ------------------------------------------------------------------
    def _build_menubar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&Bestand")

        new_action = QAction("Nieuwe job...", self)
        new_action.triggered.connect(self.on_new_job)
        file_menu.addAction(new_action)

        open_action = QAction("Job openen...", self)
        open_action.triggered.connect(self.on_open_job)
        file_menu.addAction(open_action)

        save_action = QAction("Job opslaan", self)
        save_action.triggered.connect(self.on_save_job)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        import_action = QAction("PDF-sjabloon importeren...", self)
        import_action.triggered.connect(self.on_import_pdf)
        file_menu.addAction(import_action)

        file_menu.addSeparator()
        quit_action = QAction("Afsluiten", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        edit_menu = menubar.addMenu("&Bewerken")
        # Nog niet geïmplementeerd - bewust uitgeschakeld i.p.v. een knop die
        # niets doet (dat wekt de indruk dat er iets stuk is bij het testen).
        undo_action = QAction("Ongedaan maken", self)
        undo_action.setEnabled(False)
        edit_menu.addAction(undo_action)
        redo_action = QAction("Opnieuw", self)
        redo_action.setEnabled(False)
        edit_menu.addAction(redo_action)
        edit_menu.addSeparator()
        copy_action = QAction("Kopiëren", self)
        copy_action.setEnabled(False)
        edit_menu.addAction(copy_action)
        paste_action = QAction("Plakken", self)
        paste_action.setEnabled(False)
        edit_menu.addAction(paste_action)
        duplicate_action = QAction("Dupliceren", self)
        duplicate_action.setEnabled(False)
        edit_menu.addAction(duplicate_action)

        view_menu = menubar.addMenu("&Beeld")
        zoom_in_action = QAction("Inzoomen", self)
        zoom_in_action.setEnabled(False)
        view_menu.addAction(zoom_in_action)
        zoom_out_action = QAction("Uitzoomen", self)
        zoom_out_action.setEnabled(False)
        view_menu.addAction(zoom_out_action)
        zoom_fit_action = QAction("Passend maken", self)
        zoom_fit_action.setEnabled(False)
        view_menu.addAction(zoom_fit_action)

        job_menu = menubar.addMenu("&Job")
        preflight_menu_action = QAction("Preflight uitvoeren...", self)
        preflight_menu_action.setEnabled(False)
        job_menu.addAction(preflight_menu_action)
        produce_action = QAction("Produceren...", self)
        produce_action.setEnabled(False)
        job_menu.addAction(produce_action)

    # ------------------------------------------------------------------
    def _build_toolbar(self):
        toolbar = QToolBar("Hoofdwerkbalk")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        text_action = QAction("Tekstvak", self)
        text_action.triggered.connect(self.on_add_text_placeholder)
        toolbar.addAction(text_action)

        image_action = QAction("Afbeeldingsvak", self)
        image_action.triggered.connect(self.on_add_image_placeholder)
        toolbar.addAction(image_action)

        barcode_action = QAction("Barcode/QR", self)
        barcode_action.triggered.connect(self.on_add_barcode_placeholder)
        toolbar.addAction(barcode_action)

        shape_action = QAction("Maskeervlak", self)
        shape_action.triggered.connect(self.on_add_shape_placeholder)
        toolbar.addAction(shape_action)

        toolbar.addSeparator()
        preflight_toolbar_action = QAction("Preflight", self)
        preflight_toolbar_action.setEnabled(False)
        toolbar.addAction(preflight_toolbar_action)

    # ------------------------------------------------------------------
    def _build_central_widget(self):
        self.canvas = CanvasView()
        self.canvas.on_change_callback = self._on_canvas_changed
        self.setCentralWidget(self.canvas)

    # ------------------------------------------------------------------
    def _on_canvas_changed(self):
        """Callback vanuit CanvasView (bv. na het verwijderen van een vak)."""
        self._refresh_objects_panel()
        self.mark_dirty()

    # ------------------------------------------------------------------
    def _build_docks(self):
        objects_dock = QDockWidget("Objecten", self)
        self.objects_panel = ObjectsPanel()
        objects_dock.setWidget(self.objects_panel)
        objects_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, objects_dock)

        data_dock = QDockWidget("Data", self)
        self.data_panel = DataPanel()
        self.data_panel.data_loaded.connect(self.on_data_loaded)
        self.data_panel.column_double_clicked.connect(self.on_column_double_clicked)
        data_dock.setWidget(self.data_panel)
        data_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, data_dock)

        nav_dock = QDockWidget("Recordnavigatie", self)
        self.record_nav = RecordNavigationBar()
        self.record_nav.previous_requested.connect(self.on_previous_record)
        self.record_nav.next_requested.connect(self.on_next_record)
        nav_dock.setWidget(self.record_nav)
        nav_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        nav_dock.setTitleBarWidget(QWidget())
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, nav_dock)

    # ------------------------------------------------------------------
    def _build_statusbar(self):
        self.status = QStatusBar()
        self.status.showMessage("Klaar - geen sjabloon geladen")
        self.setStatusBar(self.status)

    # ------------------------------------------------------------------
    def on_import_pdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "PDF-sjabloon importeren", "", "PDF-bestanden (*.pdf)"
        )
        if not path:
            return  # gebruiker heeft geannuleerd

        success, error = self.canvas.load_pdf(path)
        if not success:
            QMessageBox.warning(self, "Kon PDF niet laden", error)
            return

        # BUG FIX: load_pdf() wist intern canvas._all_records/_current_record
        # (want de scene - en dus alle vakken - wordt geleegd), maar
        # MainWindow.records blijft gewoon staan als er al data geladen was.
        # Zonder deze regel zou een later toegevoegd vak in fit_all_records-
        # modus geen dataset hebben om tegen te berekenen, terwijl het
        # data-paneel wel gewoon records toont - een verwarrende inconsistentie.
        self.canvas.set_records(self.records)

        filename = path.split("/")[-1]
        self.status.showMessage(f"Sjabloon geladen: {filename}")
        self._refresh_objects_panel()
        self.mark_dirty()

    # ------------------------------------------------------------------
    def on_add_text_placeholder(self):
        self.canvas.add_text_placeholder()
        self._refresh_objects_panel()
        self.mark_dirty()

    # ------------------------------------------------------------------
    def on_add_image_placeholder(self):
        self.canvas.add_image_placeholder()
        self._refresh_objects_panel()
        self.mark_dirty()

    # ------------------------------------------------------------------
    def on_add_barcode_placeholder(self):
        self.canvas.add_barcode_placeholder()
        self._refresh_objects_panel()
        self.mark_dirty()

    # ------------------------------------------------------------------
    def on_add_shape_placeholder(self):
        self.canvas.add_shape_placeholder()
        self._refresh_objects_panel()
        self.mark_dirty()

    # ------------------------------------------------------------------
    def on_data_loaded(self, filename: str, columns: list, record_count: int):
        self.records = self.data_panel.records
        self.current_index = 0 if self.records else -1

        self.record_nav.set_loaded(filename, len(columns), record_count)
        self.record_nav.set_position(max(self.current_index, 0), record_count)
        self.status.showMessage(
            f"Data geladen: {filename} ({record_count} records, {len(columns)} kolommen)"
        )

        # Afbeeldingsvakken zoeken bestandsnamen relatief aan de map van
        # de geladen CSV/Excel (tenzij de waarde zelf al een bestaand pad is).
        data_path = self.data_panel.loaded_path
        self.canvas.set_asset_base_dir(str(Path(data_path).parent) if data_path else None)

        # set_records() herberekent meteen fit_all_records-lettergroottes;
        # _apply_current_record() zorgt daarna dat het juiste record (index 0)
        # ook echt getoond wordt.
        self.canvas.set_records(self.records)

        # Kolom-mapping: als een vak gekoppeld is aan een kolomnaam die in
        # dit bestand niet bestaat, hier een koppelscherm aanbieden.
        self._check_field_mapping(columns)

        self._apply_current_record()
        self.mark_dirty()

    # ------------------------------------------------------------------
    def _get_linked_field_names(self) -> set[str]:
        """
        Alle kolomnamen waaraan minstens één vak gekoppeld is - tekstvakken
        alleen als ze op "Bron: Kolom" staan (nummering-vakken niet).
        """
        names: set[str] = set()
        for box in self.canvas.get_text_boxes():
            if box.value_source == "field" and box.field_name:
                names.add(box.field_name)
        for box in self.canvas.get_image_boxes():
            if box.field_name:
                names.add(box.field_name)
        for box in self.canvas.get_barcode_boxes():
            if box.field_name:
                names.add(box.field_name)
        return names

    def _check_field_mapping(self, columns: list[str]):
        """
        Vergelijkt de kolomnamen waar vakken al aan gekoppeld zijn met de
        kolommen van de zojuist geladen data. Bij een mismatch (bv. een
        sjabloon dat eerder met "Voornaam" is gemaakt, terwijl deze data
        "Naam1" heet) verschijnt een koppelscherm. Blijft er na het
        koppelen nog iets niet kloppen, dan volgt een duidelijke melding -
        de betrokken vakken tonen zelf ook een waarschuwing (zie
        flag_missing_columns, aangeroepen vanuit _apply_current_record).
        """
        linked = self._get_linked_field_names()
        available = set(columns)
        missing = sorted(linked - available)
        if not missing:
            return

        dialog = MappingDialog(missing, columns, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._apply_field_mapping(dialog.get_mapping())

        still_linked = self._get_linked_field_names()
        still_missing = sorted(still_linked - available)
        if still_missing:
            QMessageBox.warning(
                self,
                "Niet alle vakken zijn gekoppeld",
                "De volgende vakken zijn gekoppeld aan een kolom die niet in "
                "dit bestand voorkomt en tonen daarom een waarschuwing:\n\n"
                + "\n".join(f"- {name}" for name in still_missing)
                + "\n\nCorrigeer dit (dubbelklik op de juiste kolom in het "
                "data-paneel) voordat je deze job gaat produceren.",
            )

    def _apply_field_mapping(self, mapping: dict):
        """Past een gekozen kolomkoppeling toe op alle vakken die de oude naam gebruikten."""
        for old_name, new_name in mapping.items():
            if not new_name:
                continue  # "(geen koppeling)" gekozen - laat ongewijzigd
            for box in self.canvas.get_all_boxes():
                if getattr(box, "field_name", None) == old_name:
                    box.field_name = new_name
        self._refresh_objects_panel()
        self.mark_dirty()

    # ------------------------------------------------------------------
    def on_column_double_clicked(self, column_name: str):
        box = self.canvas.get_selected_placeholder()
        if box is None:
            QMessageBox.information(
                self,
                "Selecteer eerst een vak",
                "Klik op een tekst- of afbeeldingsvak op het canvas om het te "
                "selecteren, en dubbelklik daarna op een kolomnaam om ze te koppelen.",
            )
            return

        box.set_field(column_name)
        self._refresh_objects_panel()
        self._apply_current_record()
        self.status.showMessage(f"Vak gekoppeld aan kolom '{column_name}'")
        self.mark_dirty()

    # ------------------------------------------------------------------
    def on_previous_record(self):
        if self.current_index > 0:
            self.current_index -= 1
            self._apply_current_record()
            self.record_nav.set_position(self.current_index, len(self.records))

    def on_next_record(self):
        if self.current_index < len(self.records) - 1:
            self.current_index += 1
            self._apply_current_record()
            self.record_nav.set_position(self.current_index, len(self.records))

    # ------------------------------------------------------------------
    def _apply_current_record(self):
        record = None
        index = None
        if self.records and 0 <= self.current_index < len(self.records):
            record = self.records[self.current_index]
            index = self.current_index
        self.canvas.apply_record(record, index)
        if self.data_panel.column_names:
            self.canvas.flag_missing_columns(set(self.data_panel.column_names))
        self._refresh_objects_panel()

    def _refresh_objects_panel(self):
        self.objects_panel.object_list.clear()
        self.objects_panel.object_list.addItem("Background (locked)")
        for box in self.canvas.get_text_boxes():
            if box.value_source == "sequence":
                affix = f"{box.seq_prefix}...{box.seq_suffix}" if (box.seq_prefix or box.seq_suffix) else ""
                label = f"🔢 Nummering {affix}".strip()
            else:
                label = f"{{{{{box.field_name}}}}}" if box.field_name else "{{veld}}"
            if getattr(box, "_is_overflowing", False):
                label = f"⚠ {label} (past niet)"
            self.objects_panel.object_list.addItem(label)
        for box in self.canvas.get_image_boxes():
            label = f"🖼 {{{{{box.field_name}}}}}" if box.field_name else "🖼 afbeeldingsvak"
            if getattr(box, "_is_overflowing", False):
                label = f"⚠ {label} (niet gevonden)"
            self.objects_panel.object_list.addItem(label)
        for box in self.canvas.get_barcode_boxes():
            type_label = "QR" if box.barcode_type == "qr" else "Barcode"
            label = f"▦ {type_label} {{{{{box.field_name}}}}}" if box.field_name else f"▦ {type_label}-vak"
            if getattr(box, "_is_overflowing", False):
                label = f"⚠ {label} (kon niet genereren)"
            self.objects_panel.object_list.addItem(label)
        for box in self.canvas.get_shape_boxes():
            self.objects_panel.object_list.addItem(f"▭ Maskeervlak ({box.color})")

    # ------------------------------------------------------------------
    def mark_dirty(self):
        """Geeft aan dat de job wijzigingen bevat die nog niet opgeslagen zijn."""
        self._dirty = True

    def _confirm_discard_changes(self) -> bool:
        """
        Vraagt bevestiging als er niet-opgeslagen wijzigingen zijn.
        True = de gebruiker mag doorgaan (wijzigingen verliezen is oké).

        BEKENDE BEPERKING: het verplaatsen/resizen van een vak op het
        canvas wordt momenteel niet apart gemeld als wijziging (dat zou
        signalen vanuit de graphics-items terug naar MainWindow vereisen).
        De belangrijkste risico's - een nieuw sjabloon/vak/koppeling/data
        kwijtraken - worden wel afgedekt.
        """
        if not self._dirty:
            return True
        reply = QMessageBox.question(
            self,
            "Niet-opgeslagen wijzigingen",
            "Deze job bevat niet-opgeslagen wijzigingen. Wil je doorgaan "
            "zonder op te slaan?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def closeEvent(self, event):
        """Vraagt ook bij het afsluiten van de applicatie om bevestiging."""
        if self._confirm_discard_changes():
            event.accept()
        else:
            event.ignore()

    # ------------------------------------------------------------------
    def on_new_job(self):
        if not self._confirm_discard_changes():
            return
        self.canvas.reset()
        self.data_panel.reset()
        self.records = []
        self.current_index = -1
        self._refresh_objects_panel()
        self.record_nav.set_loaded("", 0, 0)
        self.record_nav.set_position(0, 0)
        self.status.showMessage("Nieuwe job - geen sjabloon geladen")
        self._dirty = False

    # ------------------------------------------------------------------
    def on_save_job(self):
        """
        Slaat de job op als .vdp4-package: een zip-bestand met
        manifest.json + een kopie van de PDF + een kopie van de data.
        """
        template_path = self.canvas.get_template_pdf_path()
        if not template_path:
            QMessageBox.information(
                self,
                "Geen sjabloon geladen",
                "Laad eerst een PDF-sjabloon voordat je de job opslaat.",
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Job opslaan", "", "vdp4free-project (*.vdp4)"
        )
        if not path:
            return
        if not path.lower().endswith(".vdp4"):
            path += ".vdp4"

        data_path = self.data_panel.loaded_path
        data_arcname = None
        if data_path and Path(data_path).exists():
            ext = Path(data_path).suffix or ".csv"
            data_arcname = f"data/source{ext}"

        manifest = {
            "format": "vdp4free-project",
            "version": 1,
            "template_filename": "template.pdf",
            "data_filename": data_arcname,
            "text_boxes": self.canvas.serialize_text_boxes(),
            "image_boxes": self.canvas.serialize_image_boxes(),
            "barcode_boxes": self.canvas.serialize_barcode_boxes(),
            "shape_boxes": self.canvas.serialize_shape_boxes(),
        }

        # Atomair opslaan: eerst volledig naar een .tmp-bestand schrijven en
        # pas bij succes hernoemen naar de echte bestandsnaam. Zo kan een
        # fout halverwege het schrijven nooit een al bestaand, goed job-
        # bestand beschadigen - in het ergste geval blijft alleen het .tmp-
        # bestand onvolledig achter, en het origineel (indien aanwezig)
        # blijft intact.
        tmp_path = Path(path + ".tmp")
        try:
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(
                    "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False)
                )
                zf.write(template_path, arcname="template.pdf")
                if data_arcname:
                    zf.write(data_path, arcname=data_arcname)
            tmp_path.replace(path)  # atomische hernoeming op de meeste OS'en
        except Exception as exc:  # noqa: BLE001
            tmp_path.unlink(missing_ok=True)  # eventueel half geschreven bestand opruimen
            QMessageBox.critical(self, "Kon job niet opslaan", str(exc))
            return

        self.status.showMessage(f"Job opgeslagen: {Path(path).name}")
        self._dirty = False

    # ------------------------------------------------------------------
    def on_open_job(self):
        """
        Opent een .vdp4-package: pakt manifest.json, template.pdf en
        (indien aanwezig) de databron uit naar een tijdelijke map, en
        laadt alles vanaf daar.
        """
        if not self._confirm_discard_changes():
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "Job openen", "", "vdp4free-project (*.vdp4)"
        )
        if not path:
            return

        try:
            zf = zipfile.ZipFile(path, "r")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Kon jobbestand niet openen", str(exc))
            return

        try:
            manifest = json.loads(zf.read("manifest.json"))
        except Exception:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Ongeldig jobbestand",
                "Dit .vdp4-bestand mist een manifest.json of is beschadigd.",
            )
            zf.close()
            return

        extract_dir = Path(tempfile.mkdtemp(prefix="vdp4free_"))

        template_filename = manifest.get("template_filename", "template.pdf")
        if template_filename not in zf.namelist():
            QMessageBox.critical(
                self, "Sjabloon ontbreekt", "Het jobbestand bevat geen PDF-sjabloon."
            )
            zf.close()
            return
        template_extracted_path = extract_dir / "template.pdf"
        template_extracted_path.write_bytes(zf.read(template_filename))

        data_filename = manifest.get("data_filename")
        data_extracted_path = None
        if data_filename and data_filename in zf.namelist():
            data_extracted_path = extract_dir / Path(data_filename).name
            data_extracted_path.write_bytes(zf.read(data_filename))

        zf.close()

        success, error = self.canvas.load_pdf(str(template_extracted_path))
        if not success:
            QMessageBox.warning(self, "Kon PDF niet laden", error)
            return

        self.canvas.load_text_boxes(manifest.get("text_boxes", []))
        self.canvas.load_image_boxes(manifest.get("image_boxes", []))
        self.canvas.load_barcode_boxes(manifest.get("barcode_boxes", []))
        self.canvas.load_shape_boxes(manifest.get("shape_boxes", []))

        self.records = []
        self.current_index = -1
        if data_extracted_path:
            success, error = self.data_panel.load_from_path(str(data_extracted_path))
            if not success:
                QMessageBox.warning(self, "Kon databestand niet laden", error)
        else:
            self.data_panel.reset()
            self.canvas.set_records([])
            self.canvas.set_asset_base_dir(None)
            self.record_nav.set_loaded("", 0, 0)
            self.record_nav.set_position(0, 0)

        self._refresh_objects_panel()
        self._apply_current_record()
        self.status.showMessage(f"Job geladen: {Path(path).name}")
        self._dirty = False


def check_default_font_available():
    """
    Lichte fontcontrole bij opstarten: het standaardlettertype van nieuwe
    tekstvakken is "Arial". Als dat niet echt op dit systeem geïnstalleerd
    staat, kan Qt stilzwijgend een vervangend lettertype gebruiken - en dat
    is precies wat we bij productiesoftware willen vermijden (principe:
    "nooit stille font-substitutie", zie ook de licentie-/MVP-documenten).

    Dit is bewust een simpele, globale controle bij opstarten - een volledige,
    per-vak fontcontrole (met een eigen lettertype-keuze per vak) hoort
    thuis in de toekomstige Preflight-engine, zodra er ook een UI is om het
    lettertype per vak te kiezen.
    """
    default_family = "Arial"
    available = QFontDatabase.families()
    if default_family not in available:
        QMessageBox.warning(
            None,
            "Standaardlettertype niet gevonden",
            f"Het standaardlettertype '{default_family}' lijkt niet "
            "geïnstalleerd te zijn op dit systeem. Qt gebruikt dan "
            "automatisch een vervangend lettertype voor tekstvakken.\n\n"
            "Voor productiewerk is dat risicovol: de weergave op het scherm "
            "kan afwijken van wat er straks daadwerkelijk gedrukt wordt.",
        )


def main():
    app = QApplication(sys.argv)
    check_default_font_available()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
