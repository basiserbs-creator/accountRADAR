"""
PlaceholderTextBox: het tekstvak-vaktype van vdp4free.

Zie main.py / de projectdocumentatie voor de algemene architectuur.
"""

import uuid

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QFontMetricsF, QBrush, QColor, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsTextItem,
    QFontDialog,
    QInputDialog,
    QMenu,
)


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
        element_id=None,
    ):
        super().__init__(0, 0, width, height)
        self.setPos(x, y)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setBrush(QBrush(QColor(255, 255, 255, 210)))
        self.setPen(self.NORMAL_PEN)

        # Unieke, permanente identiteit - blijft hetzelfde over opslaan/
        # laden heen (nodig zodra er later regels/condities/een API op
        # specifieke vakken gaan verwijzen, i.p.v. steeds "het 3e tekstvak").
        self.element_id = element_id or str(uuid.uuid4())

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
        # Onderscheidt een programmatische tekstwijziging (bv. tijdens
        # doorbladeren van records via show_value()) van een ECHTE
        # handmatige bewerking door de gebruiker - alleen de laatste hoort
        # de job als "gewijzigd" te markeren. Zie _set_text()/
        # _on_text_content_changed().
        self._programmatic_update = False

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

        # Sleephoekje als apart kind-element met een hoge z-waarde, zodat
        # het altijd zichtbaar blijft - ook als de tekst (bij "nooit
        # afkappen") buiten het vak uitsteekt en het anders zou bedekken.
        self.handle_item = QGraphicsRectItem(
            0, 0, self.RESIZE_HANDLE_SIZE, self.RESIZE_HANDLE_SIZE, self
        )
        self.handle_item.setBrush(QBrush(QColor(30, 100, 220)))
        self.handle_item.setPen(Qt.PenStyle.NoPen)
        self.handle_item.setZValue(10)
        self.handle_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._position_handle()

    def _position_handle(self):
        r = self.rect()
        self.handle_item.setPos(
            r.width() - self.RESIZE_HANDLE_SIZE, r.height() - self.RESIZE_HANDLE_SIZE
        )

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
            self._notify_settings_changed()
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
        front_action = menu.addAction("Naar voren brengen")
        back_action = menu.addAction("Naar achteren plaatsen")

        menu.addSeparator()
        delete_action = menu.addAction("Verwijderen")

        chosen = menu.exec(event.screenPos())
        if chosen is not None and self._canvas is not None:
            self._canvas.capture_undo_point()

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
        elif chosen == front_action:
            if self._canvas is not None:
                self._canvas.bring_to_front(self)
                self._canvas.notify_changed()
        elif chosen == back_action:
            if self._canvas is not None:
                self._canvas.send_to_back(self)
                self._canvas.notify_changed()
        elif chosen == delete_action:
            self._delete_self()

    def _configure_font(self):
        """
        Opent de systeem-lettertypekiezer (toont alleen echt op dit
        systeem geïnstalleerde fonts - dus geen risico op een niet-
        bestaand lettertype kiezen). Neemt ook meteen vet/cursief en de
        gekozen grootte over als basislettergrootte.

        Gebruikt bewust een QFontDialog-INSTANTIE met .exec()/.selectedFont()
        i.p.v. de statische QFontDialog.getFont()-gemakswrapper: die laatste
        bleek op macOS onbetrouwbaar (het native lettertypepaneel daar werkt
        niet met een klassieke OK-knop, waardoor de teruggegeven "ok"-vlag
        niet altijd klopte en een gekozen lettertype niet werd toegepast).
        """
        initial = self._make_font(self.base_font_size)
        dialog = QFontDialog()
        dialog.setCurrentFont(initial)
        if dialog.exec() != QFontDialog.DialogCode.Accepted:
            return
        chosen_font = dialog.selectedFont()
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
        self._set_text(text)
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
            self._set_text("🔢 " + self._format_sequence_value(0))
        elif self.field_name:
            self._set_text("{{" + self.field_name + "}}")
        if self.fit_mode != "fit_all_records":
            self.text_item.setFont(self._make_font(self.base_font_size))
            self._is_overflowing = False
        self._update_overflow_style()


    def show_value(self, value):
        """Toont een echte waarde uit een record (previewweergave)."""
        text = "" if value is None else str(value)
        self._set_text(text)
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
        self._set_text(f"⚠ kolom '{self.field_name}' niet gevonden")
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

    def _set_text(self, text: str):
        """
        Zet de weergegeven tekst PROGRAMMATISCH (dus niet door de
        gebruiker getypt) - bv. bij het tonen van een ander record, een
        placeholder, of een foutmelding. Gebruikt door show_value(),
        show_placeholder(), show_sequence_value() en mark_missing_column()
        i.p.v. rechtstreeks text_item.setPlainText(), zodat
        _on_text_content_changed() weet dat dit GEEN handmatige
        gebruikersbewerking is en de job dus niet als "gewijzigd" hoeft
        te markeren.
        """
        self._programmatic_update = True
        try:
            self.text_item.setPlainText(text)
        finally:
            self._programmatic_update = False

    def _on_text_content_changed(self):
        """Reageert op elke tekstwijziging - handmatig getypt of programmatisch."""
        if self.fit_mode != "fit_all_records":
            self._refit_current_text()
        if not self._programmatic_update and self._canvas is not None:
            self._canvas.notify_changed()


