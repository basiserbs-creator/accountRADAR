"""
vdp4free - opstartpunt

De applicatie is vanaf deze versie opgesplitst in meerdere bestanden
(was voorheen één bestand van ruim 3000 regels):

    main.py                 - dit bestand: opstartpunt + fontcontrole
    app_version.py          - het versienummer (zie titelbalk)
    canvas/
        text_box.py          - PlaceholderTextBox
        image_box.py          - PlaceholderImageBox
        barcode_box.py         - PlaceholderBarcodeBox
        shape_box.py            - ShapeMaskBox (maskeervlak)
        canvas_view.py           - CanvasView (bindt alle vaktypes samen)
    ui/
        objects_panel.py         - linkerpaneel (objectenlijst)
        data_panel.py              - rechterpaneel (CSV/Excel-koppeling)
        record_navigation.py         - onderbalk (recordnavigatie)
        mapping_dialog.py              - koppelscherm bij kolom-mismatch
        preflight_dialog.py              - preflight-rapportvenster
        main_window.py                     - hoofdvenster + alle handlers
    project/
        package.py                          - .vdp4-opslaan/laden + assets

Functioneel verandert er niets t.o.v. de vorige, single-file versie -
dit is een pure herstructurering ("refactor"), bedoeld om het project
beheersbaar te houden nu Output/PDF-generatie eraan komt.

Starten (ongewijzigd):
    source .venv/bin/activate
    python main.py
"""

import sys

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QMessageBox

from ui.main_window import MainWindow


def check_default_font_available():
    """
    Lichte fontcontrole bij opstarten: het standaardlettertype van nieuwe
    tekstvakken is "Arial". Als dat niet echt op dit systeem geïnstalleerd
    staat, kan Qt stilzwijgend een vervangend lettertype gebruiken - en dat
    is precies wat we bij productiesoftware willen vermijden (principe:
    "nooit stille font-substitutie").

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
