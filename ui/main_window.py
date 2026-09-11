"""
MainWindow: het hoofdvenster van vdp4free - menubalk, werkbalk, panelen,
en alle event-handlers die alles met elkaar verbinden.
"""

from pathlib import Path

import barcode
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFontDatabase, QFontMetricsF, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QToolBar,
    QWidget,
)

from app_version import APP_VERSION
from canvas.barcode_box import PlaceholderBarcodeBox
from canvas.canvas_view import CanvasView
from canvas.image_box import PlaceholderImageBox
from canvas.shape_box import ShapeMaskBox
from canvas.text_box import PlaceholderTextBox
from project.package import open_job, save_job
from ui.data_panel import DataPanel
from ui.mapping_dialog import MappingDialog
from ui.objects_panel import ObjectsPanel
from ui.preflight_dialog import PreflightDialog
from ui.record_navigation import RecordNavigationBar


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"vdp4free (werknaam) - PDF-canvas - {APP_VERSION}")
        self.resize(1200, 800)

        self.current_index: int = -1
        self._dirty = False  # niet-opgeslagen wijzigingen? zie mark_dirty()

        # Undo/redo: snapshot-gebaseerd (niet per-actie-commando's) - simpeler
        # en werkt uniform voor alle vaktypes. Zie CanvasView.get_snapshot()/
        # restore_snapshot() en capture_undo_point().
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._max_undo_depth = 50

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
        self.undo_action = QAction("Ongedaan maken", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.setEnabled(False)  # tot er iets op de undo-stack staat
        self.undo_action.triggered.connect(self.on_undo)
        edit_menu.addAction(self.undo_action)

        self.redo_action = QAction("Opnieuw", self)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.setEnabled(False)
        self.redo_action.triggered.connect(self.on_redo)
        edit_menu.addAction(self.redo_action)

        edit_menu.addSeparator()
        # Deze drie zijn nog niet geïmplementeerd - bewust uitgeschakeld
        # i.p.v. een knop die niets doet (dat wekt de indruk dat er iets
        # stuk is bij het testen).
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
        preflight_menu_action.triggered.connect(self.on_run_preflight)
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
        preflight_toolbar_action.triggered.connect(self.on_run_preflight)
        toolbar.addAction(preflight_toolbar_action)

    # ------------------------------------------------------------------
    def _build_central_widget(self):
        self.canvas = CanvasView()
        self.canvas.on_change_callback = self._on_canvas_changed
        self.canvas.on_before_change_callback = self._push_undo_snapshot
        self.setCentralWidget(self.canvas)

    # ------------------------------------------------------------------
    @property
    def records(self) -> list:
        """
        Leest ALTIJD rechtstreeks van self.data_panel.records - dit is
        bewust GEEN eigen kopie/attribuut. Een kritische reviewopmerking
        signaleerde dat er drie plekken waren die elk hun eigen
        recordlijst bijhielden (DataPanel, MainWindow, CanvasView), wat
        al één keer tot een echte bug leidde (zie de bugfix-comment bij
        on_import_pdf hieronder). Deze property elimineert MainWindow's
        eigen kopie: er is nu nog maar één "source of truth" voor de
        data zelf (DataPanel), en CanvasView._all_records blijft een
        bewuste, losse werkkopie (nodig voor de fit_all_records-
        berekening), expliciet bijgewerkt via canvas.set_records().
        """
        return self.data_panel.records

    # ------------------------------------------------------------------
    def _on_canvas_changed(self):
        """Callback vanuit CanvasView (bv. na het verwijderen van een vak)."""
        self._refresh_objects_panel()
        self.mark_dirty()

    # ------------------------------------------------------------------
    def _build_docks(self):
        objects_dock = QDockWidget("Objecten", self)
        self.objects_panel = ObjectsPanel()
        self.objects_panel.item_selected.connect(self.on_object_item_selected)
        self.objects_panel.order_changed.connect(self.on_objects_reordered)
        objects_dock.setWidget(self.objects_panel)
        objects_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, objects_dock)

        # Omgekeerde koppeling: een selectie op het CANVAS (klik op een
        # vak) licht de bijbehorende regel in het objectenpaneel op.
        self.canvas._scene.selectionChanged.connect(self._on_canvas_selection_changed)

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
        # Waarschuwen als er al vakken op het canvas staan - load_pdf()
        # wist de hele scene (dus ook alle geplaatste vakken), en zonder
        # deze check kon je per ongeluk je hele opmaak kwijtraken door
        # simpelweg een ander/nieuw PDF-sjabloon te kiezen. "Nieuwe job"
        # en "Job openen" hadden deze bescherming al, PDF-import nog niet.
        existing_boxes = self.canvas.get_all_boxes() + self.canvas.get_shape_boxes()
        if existing_boxes:
            reply = QMessageBox.question(
                self,
                "Sjabloon vervangen?",
                "Het vervangen van het PDF-sjabloon verwijdert alle vakken "
                "die al op de huidige pagina staan. Doorgaan?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

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
        self.canvas.capture_undo_point()
        self.canvas.add_text_placeholder()
        self._refresh_objects_panel()
        self.mark_dirty()

    # ------------------------------------------------------------------
    def on_add_image_placeholder(self):
        self.canvas.capture_undo_point()
        self.canvas.add_image_placeholder()
        self._refresh_objects_panel()
        self.mark_dirty()

    # ------------------------------------------------------------------
    def on_add_barcode_placeholder(self):
        self.canvas.capture_undo_point()
        self.canvas.add_barcode_placeholder()
        self._refresh_objects_panel()
        self.mark_dirty()

    # ------------------------------------------------------------------
    def on_add_shape_placeholder(self):
        self.canvas.capture_undo_point()
        self.canvas.add_shape_placeholder()
        self._refresh_objects_panel()
        self.mark_dirty()

    # ------------------------------------------------------------------
    def on_data_loaded(self, filename: str, columns: list, record_count: int):
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
        self.canvas.capture_undo_point()
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

        self.canvas.capture_undo_point()
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
    def on_run_preflight(self):
        result = self.run_preflight()
        dialog = PreflightDialog(result, self)
        dialog.exec()

    def run_preflight(self) -> dict:
        """
        Doorloopt de VOLLEDIGE dataset (niet alleen het huidige record) en
        controleert op productieklaarheid: structurele koppelfouten, lege
        verplichte velden, tekst die niet past, ontbrekende afbeeldingen,
        ongeldige barcodes/QR-waarden, en ontbrekende lettertypes.

        Geeft een dict terug (zie PreflightDialog._format_report voor de
        exacte sleutels) - dit is bewust een pure functie zonder UI, zodat
        de logica ook los van het dialoogvenster getest kan worden.
        """
        MAX_EXAMPLES = 20

        result = {
            "record_count": len(self.records),
            "no_data": not self.records,
            "structural_issues": [],
            "missing_field_count": 0,
            "missing_field_examples": [],
            "text_overflow_count": 0,
            "text_overflow_examples": [],
            "missing_image_count": 0,
            "missing_image_examples": [],
            "invalid_barcode_count": 0,
            "invalid_barcode_examples": [],
            "missing_fonts": set(),
        }

        if result["no_data"]:
            result["is_ready"] = False
            return result

        columns = set(self.data_panel.column_names)
        all_boxes = self.canvas.get_all_boxes()

        if not all_boxes:
            result["structural_issues"].append(
                "Geen vakken op het canvas - er is niets om te controleren."
            )

        # 1. Structurele koppelfouten: kolom bestaat helemaal niet, of vak
        #    is nooit gekoppeld aan iets.
        for box in all_boxes:
            if isinstance(box, PlaceholderTextBox) and box.value_source != "field":
                continue  # nummering-vakken zijn niet kolom-gebonden
            field_name = getattr(box, "field_name", None)
            if not field_name:
                result["structural_issues"].append(
                    f"Een {self._box_type_label(box)} is nog niet gekoppeld aan een kolom"
                )
            elif field_name not in columns:
                result["structural_issues"].append(
                    f"Vak gekoppeld aan kolom '{field_name}', die niet in de data voorkomt"
                )

        # 2. Lettertype-beschikbaarheid (eenmalige, dataset-onafhankelijke check)
        available_fonts = set(QFontDatabase.families())
        for box in self.canvas.get_text_boxes():
            if box.font_family not in available_fonts:
                result["missing_fonts"].add(box.font_family)

        # 3. Per record: lege velden, tekstoverflow, ontbrekende afbeeldingen,
        #    ongeldige barcodes - alleen voor vakken met een geldige koppeling
        #    (structurele fouten zijn hierboven al gemeld).
        for idx, record in enumerate(self.records):
            record_num = idx + 1

            for box in self.canvas.get_text_boxes():
                if box.value_source != "field":
                    continue
                field_name = box.field_name
                if not field_name or field_name not in columns:
                    continue
                value = record.get(field_name, "")
                text = "" if value is None else str(value)
                if not text.strip():
                    result["missing_field_count"] += 1
                    if len(result["missing_field_examples"]) < MAX_EXAMPLES:
                        result["missing_field_examples"].append((record_num, field_name))
                    continue
                if self._check_text_overflow(box, text):
                    result["text_overflow_count"] += 1
                    if len(result["text_overflow_examples"]) < MAX_EXAMPLES:
                        result["text_overflow_examples"].append((record_num, field_name, text))

            for box in self.canvas.get_image_boxes():
                field_name = box.field_name
                if not field_name or field_name not in columns:
                    continue
                value = record.get(field_name, "")
                filename = "" if value is None else str(value).strip()
                if not filename:
                    result["missing_image_count"] += 1
                    if len(result["missing_image_examples"]) < MAX_EXAMPLES:
                        result["missing_image_examples"].append((record_num, field_name, "(leeg veld)"))
                    continue
                if not self.canvas.resolve_asset_path(filename):
                    result["missing_image_count"] += 1
                    if len(result["missing_image_examples"]) < MAX_EXAMPLES:
                        result["missing_image_examples"].append((record_num, field_name, filename))

            for box in self.canvas.get_barcode_boxes():
                field_name = box.field_name
                if not field_name or field_name not in columns:
                    continue
                value = record.get(field_name, "")
                text = "" if value is None else str(value).strip()
                if not text:
                    result["invalid_barcode_count"] += 1
                    if len(result["invalid_barcode_examples"]) < MAX_EXAMPLES:
                        result["invalid_barcode_examples"].append((record_num, field_name, "(leeg veld)"))
                    continue
                if box.barcode_type == "code128":
                    try:
                        barcode.get_barcode_class("code128")(text)
                    except Exception as exc:  # noqa: BLE001
                        result["invalid_barcode_count"] += 1
                        if len(result["invalid_barcode_examples"]) < MAX_EXAMPLES:
                            result["invalid_barcode_examples"].append((record_num, field_name, str(exc)))
                # QR-codes zijn vrijwel altijd geldig (elke tekst kan
                # gecodeerd worden) - geen aparte check nodig.

        result["is_ready"] = (
            not result["structural_issues"]
            and result["missing_field_count"] == 0
            and result["text_overflow_count"] == 0
            and result["missing_image_count"] == 0
            and result["invalid_barcode_count"] == 0
            and not result["missing_fonts"]
        )
        return result

    @staticmethod
    def _box_type_label(box) -> str:
        if isinstance(box, PlaceholderTextBox):
            return "tekstvak"
        if isinstance(box, PlaceholderImageBox):
            return "afbeeldingsvak"
        if isinstance(box, PlaceholderBarcodeBox):
            return "barcode/QR-vak"
        return "vak"

    @staticmethod
    def _check_text_overflow(box, text: str) -> bool:
        """
        Bepaalt of `text` in `box` zou passen, ZONDER de weergave van het
        vak te wijzigen (preflight mag het huidige, zichtbare record niet
        verstoren). Hergebruikt bewust dezelfde berekeningen als de
        live-preview, zodat preflight en weergave nooit tegenspreken.
        """
        if box.fit_mode == "fixed":
            font = box._make_font(box.base_font_size)
            metrics = QFontMetricsF(font)
            fits_width = metrics.horizontalAdvance(text) <= box._available_width()
            fits_height = metrics.height() <= box._available_height()
            return not (fits_width and fits_height)
        elif box.fit_mode == "shrink_to_fit":
            _, overflow = box._compute_fitting_font_size([text])
            return overflow
        else:  # fit_all_records - dataset-brede, al eerder berekende vlag
            return box._is_overflowing

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
        entries = []
        for box in self.canvas.get_stacked_boxes():
            entries.append((self._label_for_box(box), box))
        entries.append(("Background", None))  # altijd onderaan, niet sleepbaar/selecteerbaar
        self.objects_panel.set_objects(entries)

    @staticmethod
    def _label_for_box(box) -> str:
        if isinstance(box, PlaceholderTextBox):
            if box.value_source == "sequence":
                affix = f"{box.seq_prefix}...{box.seq_suffix}" if (box.seq_prefix or box.seq_suffix) else ""
                label = f"🔢 Nummering {affix}".strip()
            else:
                label = f"{{{{{box.field_name}}}}}" if box.field_name else "{{veld}}"
            if getattr(box, "_is_overflowing", False):
                label = f"⚠ {label} (past niet)"
            return label
        if isinstance(box, PlaceholderImageBox):
            label = f"🖼 {{{{{box.field_name}}}}}" if box.field_name else "🖼 afbeeldingsvak"
            if getattr(box, "_is_overflowing", False):
                label = f"⚠ {label} (niet gevonden)"
            return label
        if isinstance(box, PlaceholderBarcodeBox):
            type_label = "QR" if box.barcode_type == "qr" else "Barcode"
            label = f"▦ {type_label} {{{{{box.field_name}}}}}" if box.field_name else f"▦ {type_label}-vak"
            if getattr(box, "_is_overflowing", False):
                label = f"⚠ {label} (kon niet genereren)"
            return label
        if isinstance(box, ShapeMaskBox):
            return f"▭ Maskeervlak ({box.color})"
        return "Onbekend vak"

    # ------------------------------------------------------------------
    def on_object_item_selected(self, box):
        """Klik op een regel in het objectenpaneel -> selecteert dat vak op het canvas."""
        self.canvas._scene.clearSelection()
        box.setSelected(True)

    def on_objects_reordered(self, boxes_top_to_bottom: list):
        """
        Na het slepen van een regel in het objectenpaneel: normaliseert
        de z-waarde EN stack_order van ALLE vakken naar een schone,
        ondubbelzinnige reeks die overeenkomt met de nieuwe volgorde in
        de lijst. Dit lost meteen ook eventuele restanten van de
        "gelijke z-waarde"-dubbelzinnigheid op (zie de eerder gevonden
        laagvolgorde-bug) - na een handmatige herordening is er geen
        ambiguïteit meer over.
        """
        self.canvas.capture_undo_point()
        n = len(boxes_top_to_bottom)
        for i, box in enumerate(boxes_top_to_bottom):
            order_value = n - i  # bovenste regel = hoogste waarde
            box.setZValue(order_value)
            box.stack_order = order_value
        self._refresh_objects_panel()
        self.mark_dirty()

    def _on_canvas_selection_changed(self):
        """Selectie op het CANVAS -> licht de bijbehorende regel in het objectenpaneel op."""
        selected = [item for item in self.canvas._scene.selectedItems() if hasattr(item, "element_id")]
        if len(selected) == 1:
            self.objects_panel.highlight_box(selected[0])
        else:
            self.objects_panel.highlight_box(None)

    # ------------------------------------------------------------------
    def _push_undo_snapshot(self):
        """
        Callback vanuit CanvasView.capture_undo_point() - legt de HUIDIGE
        staat vast (dus van vóór de zojuist gestarte wijziging) op de
        undo-stack. Een nieuwe wijziging maakt de redo-geschiedenis
        ongeldig, zoals gebruikelijk bij undo/redo.
        """
        snapshot = self.canvas.get_snapshot()
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > self._max_undo_depth:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._update_undo_redo_actions()

    def _update_undo_redo_actions(self):
        self.undo_action.setEnabled(bool(self._undo_stack))
        self.redo_action.setEnabled(bool(self._redo_stack))

    def _after_canvas_restore(self):
        """Gemeenschappelijke UI-verversing na een undo- of redo-stap."""
        self._refresh_objects_panel()
        if self.data_panel.column_names:
            self.canvas.flag_missing_columns(set(self.data_panel.column_names))
        self.mark_dirty()
        self._update_undo_redo_actions()

    def on_undo(self):
        if not self._undo_stack:
            return
        current = self.canvas.get_snapshot()
        snapshot = self._undo_stack.pop()
        self._redo_stack.append(current)
        self.canvas.restore_snapshot(snapshot)
        self._after_canvas_restore()
        self.status.showMessage("Ongedaan gemaakt")

    def on_redo(self):
        if not self._redo_stack:
            return
        current = self.canvas.get_snapshot()
        snapshot = self._redo_stack.pop()
        self._undo_stack.append(snapshot)
        self.canvas.restore_snapshot(snapshot)
        self._after_canvas_restore()
        self.status.showMessage("Opnieuw uitgevoerd")

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
        self.current_index = -1
        self._refresh_objects_panel()
        self.record_nav.set_loaded("", 0, 0)
        self.record_nav.set_position(0, 0)
        self.status.showMessage("Nieuwe job - geen sjabloon geladen")
        self._dirty = False
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._update_undo_redo_actions()

    # ------------------------------------------------------------------
    def on_save_job(self):
        """
        Slaat de job op als .vdp4-package (zie project/package.py voor de
        daadwerkelijke zip-/asset-logica - inclusief gebundelde
        afbeeldingen sinds deze versie).
        """
        if not self.canvas.get_template_pdf_path():
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

        try:
            save_job(self.canvas, self.data_panel, path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Kon job niet opslaan", str(exc))
            return

        self.status.showMessage(f"Job opgeslagen: {Path(path).name}")
        self._dirty = False

    # ------------------------------------------------------------------
    def on_open_job(self):
        """
        Opent een .vdp4-package (zie project/package.py voor de
        daadwerkelijke uitpak-/asset-logica) en laadt alles op het canvas.
        """
        if not self._confirm_discard_changes():
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "Job openen", "", "vdp4free-project (*.vdp4)"
        )
        if not path:
            return

        try:
            opened = open_job(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Kon jobbestand niet openen", str(exc))
            return

        manifest = opened["manifest"]

        success, error = self.canvas.load_pdf(opened["template_path"])
        if not success:
            QMessageBox.warning(self, "Kon PDF niet laden", error)
            return

        # Asset-mapping toepassen VOORDAT records/afbeeldingen getoond
        # worden - lost de v2-bug op waarbij afbeeldingen met dezelfde
        # bestandsnaam uit verschillende bronmappen elkaar konden
        # overschrijven (zie project/package.py).
        self.canvas.set_asset_mapping(opened.get("asset_mapping"))

        self.canvas.load_all_boxes(manifest)

        self.current_index = -1
        data_path = opened["data_path"]
        if data_path:
            success, error = self.data_panel.load_from_path(data_path)
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
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._update_undo_redo_actions()


