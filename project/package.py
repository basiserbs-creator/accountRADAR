"""
.vdp4-package: opslaan en laden van een job als zelfstandig zip-bestand.

ASSET-BUNDELING (v3, herzien na review van build 17):
Gebonden afbeeldingen worden in het .vdp4-bestand meegenomen onder een
CONTENT-HASH-naam (assets/<sha256-prefix>.<ext>), met in het manifest een
expliciete mapping {waarde_zoals_in_de_data: interne_bestandsnaam}.

Waarom niet gewoon de originele bestandsnaam gebruiken (zoals v2 deed)?
Twee bugs die dat veroorzaakte, en die deze aanpak allebei oplost:
1. Een waarde als "customerA/photo.jpg" bevat een submap - na het
   uitpakken bestaat dat pad niet meer, dus de oude aanpak (enkel de
   bestandsnaam gebruiken) verloor de koppeling.
2. Twee records met toevallig dezelfde bestandsnaam maar uit verschillende
   bronmappen (bv. "customerA/foto.jpg" en "customerB/foto.jpg")
   overschreven elkaar stilzwijgend in het platte assets/-archief - een
   stille datafout, precies wat dit project overal probeert te vermijden.

Met een expliciete {waarde: interne_naam}-mapping in het manifest is de
koppeling altijd ondubbelzinnig, ongeacht de oorspronkelijke padstructuur.
Content-hashing als interne naam heeft als bijkomend voordeel dat
identieke bestanden (zelfde inhoud) automatisch maar één keer opgeslagen
worden.

Deze module doet puur de bestands-I/O (zip lezen/schrijven, hashing,
paden resolven). De UI-orkestratie blijft in ui/main_window.py.
"""

import hashlib
import json
import tempfile
import zipfile
from pathlib import Path


def save_job(canvas, data_panel, path: str) -> None:
    """
    Slaat de huidige job op als .vdp4-package (atomair: eerst naar een
    .tmp-bestand, pas bij volledig succes hernoemen). Raises een
    Exception als het niet lukt - de aanroeper vangt dit af en toont een
    passende foutmelding.
    """
    template_path = canvas.get_template_pdf_path()
    if not template_path:
        raise ValueError("Geen sjabloon geladen - laad eerst een PDF-sjabloon.")

    data_path = data_panel.loaded_path
    data_arcname = None
    if data_path and Path(data_path).exists():
        ext = Path(data_path).suffix or ".csv"
        data_arcname = f"data/source{ext}"

    # {waarde_zoals_in_de_data: (interne_arcname, pad_op_schijf)}
    assets = _collect_asset_files(canvas, data_panel)

    manifest = {
        "format": "vdp4free-project",
        "version": 3,  # v3: hash-gebaseerde assets/-mapping (lost v2-bugs op)
        "template_filename": "template.pdf",
        "data_filename": data_arcname,
        "assets": {value: arcname for value, (arcname, _) in assets.items()},
        "text_boxes": canvas.serialize_text_boxes(),
        "image_boxes": canvas.serialize_image_boxes(),
        "barcode_boxes": canvas.serialize_barcode_boxes(),
        "shape_boxes": canvas.serialize_shape_boxes(),
    }

    tmp_path = Path(str(path) + ".tmp")
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
            zf.write(template_path, arcname="template.pdf")
            if data_arcname:
                zf.write(data_path, arcname=data_arcname)
            written_arcnames = set()
            for value, (arcname, disk_path) in assets.items():
                if arcname in written_arcnames:
                    continue  # zelfde inhoud (hash) al toegevoegd - dedupliceren
                zf.write(disk_path, arcname=arcname)
                written_arcnames.add(arcname)
        tmp_path.replace(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)  # eventueel half geschreven bestand opruimen
        raise


def _collect_asset_files(canvas, data_panel) -> dict:
    """
    Verzamelt alle unieke waarden die afbeeldingsvakken over de VOLLEDIGE
    dataset zouden gebruiken (niet alleen het huidige record), resolvet
    ze naar echte bestanden op schijf (via canvas.resolve_asset_path(),
    dezelfde functie als de live preview gebruikt), en geeft per waarde
    een content-hash-gebaseerde interne bestandsnaam.

    Geeft {waarde_uit_de_data: (arcname, pad_op_schijf)} terug. Waarden
    die niet gevonden kunnen worden, worden overgeslagen (dat wordt al
    gemeld via preflight/de rode rand op het vak).
    """
    result = {}
    image_boxes = canvas.get_image_boxes()
    if not image_boxes or not data_panel.records:
        return result

    needed_values = set()
    for box in image_boxes:
        if not box.field_name:
            continue
        for record in data_panel.records:
            value = record.get(box.field_name)
            text = "" if value is None else str(value).strip()
            if text:
                needed_values.add(text)

    for value in needed_values:
        resolved = canvas.resolve_asset_path(value)
        if not resolved:
            continue
        digest = _hash_file(resolved)
        ext = Path(resolved).suffix
        arcname = f"assets/{digest}{ext}"
        result[value] = (arcname, resolved)

    return result


def _hash_file(path: str, length: int = 16) -> str:
    """Korte, maar praktisch botsingsvrije content-hash van een bestand."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 64), b""):
            h.update(chunk)
    return h.hexdigest()[:length]


def open_job(path: str) -> dict:
    """
    Pakt een .vdp4-package uit naar een nieuwe tijdelijke map. Geeft een
    dict terug met:
        "manifest"       - het volledige manifest.json als dict
        "template_path"  - pad naar de uitgepakte template.pdf
        "data_path"      - pad naar de uitgepakte data, of None
        "extract_dir"    - de tijdelijke map zelf
        "asset_mapping"  - {waarde_uit_de_data: uitgepakt_pad}, klaar om
                            direct aan canvas.set_asset_mapping() te geven

    Ondersteunt zowel v3-bestanden (met expliciete assets-mapping) als
    oudere v2-bestanden (platte assets/-map, geen mapping in het manifest -
    die worden nog steeds uitgepakt, val terug op naam-gebaseerde
    resolutie zoals voorheen; de onderliggende v2-bug voor bestanden die
    toen al een naamsbotsing hadden is met terugwerkende kracht niet meer
    op te lossen, maar nieuwe jobs gebruiken vanaf nu altijd v3).

    Raises een Exception bij falen (ongeldig zip-bestand, geen
    manifest.json, ontbrekend sjabloon) - de aanroeper vangt dit af.
    """
    with zipfile.ZipFile(path, "r") as zf:
        manifest = json.loads(zf.read("manifest.json"))

        extract_dir = Path(tempfile.mkdtemp(prefix="vdp4free_"))
        names = zf.namelist()

        template_filename = manifest.get("template_filename", "template.pdf")
        if template_filename not in names:
            raise ValueError("Het jobbestand bevat geen PDF-sjabloon.")
        template_path = extract_dir / "template.pdf"
        template_path.write_bytes(zf.read(template_filename))

        data_filename = manifest.get("data_filename")
        data_path = None
        if data_filename and data_filename in names:
            data_path = extract_dir / Path(data_filename).name
            data_path.write_bytes(zf.read(data_filename))

        asset_mapping = {}
        assets_info = manifest.get("assets", {})  # waarde -> arcname (v3)

        if assets_info:
            for value, arcname in assets_info.items():
                if arcname not in names:
                    continue
                target = extract_dir / Path(arcname).name
                if not target.exists():
                    target.write_bytes(zf.read(arcname))
                asset_mapping[value] = str(target)
        else:
            # Backward compat met v2 (platte assets/-map, geen mapping):
            # gewoon uitpakken, resolutie valt terug op de bestandsnaam-
            # gebaseerde aanpak in CanvasView.resolve_asset_path().
            for name in names:
                if name.startswith("assets/") and not name.endswith("/"):
                    target = extract_dir / Path(name).name
                    if not target.exists():
                        target.write_bytes(zf.read(name))

    return {
        "manifest": manifest,
        "template_path": str(template_path),
        "data_path": str(data_path) if data_path else None,
        "extract_dir": str(extract_dir),
        "asset_mapping": asset_mapping,
    }
