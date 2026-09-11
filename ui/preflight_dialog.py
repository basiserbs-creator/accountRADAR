"""
PreflightDialog: toont het resultaat van een preflight-controle.
"""

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextEdit, QVBoxLayout


class PreflightDialog(QDialog):
    """
    Toont het resultaat van een preflight-controle: een samenvatting per
    categorie (✓/✕) met aantallen, een duidelijke productieklaar-status,
    en per categorie een paar concrete voorbeelden (recordnummer + wat
    er mis is) zodat de gebruiker weet waar te beginnen met corrigeren.
    """

    def __init__(self, result: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preflight")
        self.setMinimumSize(520, 480)

        layout = QVBoxLayout(self)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFontFamily("Courier")
        text_edit.setPlainText(self._format_report(result))
        layout.addWidget(text_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        layout.addWidget(buttons)

    @staticmethod
    def _format_report(result: dict) -> str:
        if result.get("no_data"):
            return (
                "PREFLIGHT\n"
                "=========\n\n"
                "Geen data geladen. Laad eerst een CSV- of Excel-bestand "
                "voordat je een preflight uitvoert."
            )

        lines = []
        lines.append("PREFLIGHT")
        lines.append("=========")
        lines.append("")
        lines.append(f"{result['record_count']} record(en) gevonden")
        lines.append("")

        def mark(ok):
            return "✓" if ok else "✕"

        no_structural = not result["structural_issues"]
        lines.append(f"{mark(no_structural)} Sjabloon-structuur in orde")
        if result["structural_issues"]:
            for issue in result["structural_issues"]:
                lines.append(f"    - {issue}")

        no_missing_fields = result["missing_field_count"] == 0
        lines.append(
            f"{mark(no_missing_fields)} Geen lege verplichte velden "
            f"({result['missing_field_count']} gevonden)"
        )
        for record_num, field_name in result["missing_field_examples"]:
            lines.append(f"    - Record {record_num}: '{field_name}' is leeg")
        if result["missing_field_count"] > len(result["missing_field_examples"]):
            rest = result["missing_field_count"] - len(result["missing_field_examples"])
            lines.append(f"    ... en nog {rest} meer")

        no_overflow = result["text_overflow_count"] == 0
        lines.append(
            f"{mark(no_overflow)} Geen tekst-overflows "
            f"({result['text_overflow_count']} gevonden)"
        )
        for record_num, field_name, text in result["text_overflow_examples"]:
            preview = text if len(text) <= 40 else text[:37] + "..."
            lines.append(f"    - Record {record_num}: '{field_name}' = \"{preview}\" past niet")
        if result["text_overflow_count"] > len(result["text_overflow_examples"]):
            rest = result["text_overflow_count"] - len(result["text_overflow_examples"])
            lines.append(f"    ... en nog {rest} meer")

        no_missing_images = result["missing_image_count"] == 0
        lines.append(
            f"{mark(no_missing_images)} Geen ontbrekende afbeeldingen "
            f"({result['missing_image_count']} gevonden)"
        )
        for record_num, field_name, filename in result["missing_image_examples"]:
            lines.append(f"    - Record {record_num}: '{field_name}' = \"{filename}\" niet gevonden")
        if result["missing_image_count"] > len(result["missing_image_examples"]):
            rest = result["missing_image_count"] - len(result["missing_image_examples"])
            lines.append(f"    ... en nog {rest} meer")

        no_invalid_barcodes = result["invalid_barcode_count"] == 0
        lines.append(
            f"{mark(no_invalid_barcodes)} Alle barcodes/QR-codes geldig "
            f"({result['invalid_barcode_count']} ongeldig)"
        )
        for record_num, field_name, detail in result["invalid_barcode_examples"]:
            lines.append(f"    - Record {record_num}: '{field_name}' - {detail}")
        if result["invalid_barcode_count"] > len(result["invalid_barcode_examples"]):
            rest = result["invalid_barcode_count"] - len(result["invalid_barcode_examples"])
            lines.append(f"    ... en nog {rest} meer")

        no_missing_fonts = not result["missing_fonts"]
        lines.append(
            f"{mark(no_missing_fonts)} Alle gebruikte lettertypes beschikbaar "
            f"({len(result['missing_fonts'])} ontbrekend)"
        )
        for font_name in sorted(result["missing_fonts"]):
            lines.append(f"    - '{font_name}' staat niet op dit systeem geïnstalleerd")

        lines.append("")
        if result["is_ready"]:
            lines.append("Status: ✓ PRODUCTIEKLAAR")
        else:
            lines.append("Status: ✕ NIET PRODUCTIEKLAAR")
            lines.append("")
            lines.append("Corrigeer de bovenstaande punten voordat je deze job produceert.")

        return "\n".join(lines)


