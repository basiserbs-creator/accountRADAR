"""
MappingDialog: koppelscherm bij afwijkende kolomnamen tussen sjabloon en
databron.
"""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)


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


