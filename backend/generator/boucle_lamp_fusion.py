#!/usr/bin/env python3
"""Export the complete Bouclé Stack lamp as an Autodesk Fusion mesh package.

The source geometry is mesh-native, so this package preserves the exact
production-resolution watertight meshes as named Fusion mesh components. It
does not claim to be a native parametric F3D or analytic STEP model.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

import trimesh
from trimesh.exchange.obj import export_obj
from trimesh.visual.material import SimpleMaterial
from trimesh.visual.texture import TextureVisuals

GENERATOR_DIR = Path(__file__).resolve().parent
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

import boucle_lamp_assembly as assembly  # noqa: E402
import boucle_lamp_coupons as coupons  # noqa: E402
from pipeline import load_palette, resolve_filament  # noqa: E402


OBJ_NAME = "Boucle_Stack_Lamp_Fusion_Assembly.obj"
MTL_NAME = "Boucle_Stack_Lamp_Fusion_Assembly.mtl"
THREE_MF_NAME = "Boucle_Stack_Lamp_Fusion_Assembly.3mf"
MANIFEST_NAME = "fusion_manifest.json"
README_NAME = "README.md"
ZIP_NAME = "Boucle_Stack_Lamp_Autodesk_Fusion_Package.zip"
SCRIPT_DIR_NAME = "FusionImportBoucleStack"

PART_STEMS = {
    "Leg frame": "01_Leg_Frame",
    "LED cradle": "02_LED_Cradle",
    "Diffuser baffle": "03_Diffuser_Baffle",
    "Shell A": "04_Shell_A",
    "Halo ring A–B": "05_Halo_Ring_A_to_B",
    "Shell B": "06_Shell_B",
    "Halo ring B–C": "07_Halo_Ring_B_to_C",
    "Shell C": "08_Shell_C",
    "LED module (reference)": "09_LED_Module_Reference",
}


def material_name(piece: assembly.Piece) -> str:
    if piece.label == "Diffuser baffle":
        return "Jade_White_PLA_Basic"
    if piece.label == "LED module (reference)":
        return "LED_Module_Reference"
    if piece.extruder == 1:
        return "Bone_White_PLA_Matte"
    return "Dark_Chocolate_PLA_Matte"


def exact_assembly() -> tuple[list[assembly.Piece], dict]:
    pieces, report = assembly.build_assembly(
        sections=coupons.SECTIONS,
        profile_stride=1,
        ring_steps=260,
        include_led_reference=True,
    )
    for piece in pieces:
        piece.mesh = coupons._serialization_safe(
            piece.mesh,
            f"Fusion {piece.label}",
        )
    labels = {piece.label for piece in pieces}
    if labels != set(PART_STEMS):
        raise RuntimeError(
            "Fusion export part list drifted from the expected assembly: "
            f"{sorted(labels)}"
        )
    report["model"] = "Bouclé Stack lamp — Autodesk Fusion exact mesh assembly"
    report["note"] = (
        "Production-resolution watertight mesh components in finished assembly "
        "positions; not a print layout or native parametric B-Rep."
    )
    return pieces, report


def write_components(
    pieces: list[assembly.Piece],
    out_dir: Path,
) -> tuple[Path, list[dict]]:
    component_dir = out_dir / "components"
    component_dir.mkdir(parents=True, exist_ok=True)
    for stale in component_dir.iterdir():
        if stale.is_file() and stale.suffix.lower() in {".obj", ".stl"}:
            stale.unlink()
    records: list[dict] = []
    for piece in pieces:
        stem = PART_STEMS[piece.label]
        path = component_dir / f"{stem}.obj"
        path.write_text(
            export_obj(
                piece.mesh,
                include_normals=True,
                include_color=False,
                include_texture=False,
                digits=10,
                header=(
                    f"{piece.label}; units are millimetres; "
                    "coordinates are the finished assembly position"
                ),
            ),
            encoding="utf-8",
        )
        reloaded = trimesh.load_mesh(path, process=True)
        if (
            not isinstance(reloaded, trimesh.Trimesh)
            or not reloaded.is_watertight
            or not reloaded.is_volume
        ):
            raise RuntimeError(f"Fusion component is not a closed volume: {path}")
        records.append(
            {
                "index": len(records) + 1,
                "name": piece.label,
                "file": str(path.relative_to(out_dir)),
                "printed_part": piece.printed,
                "material": material_name(piece),
                "units": "mm",
                "coordinates": "finished assembly position",
                "triangle_count": int(len(piece.mesh.faces)),
                "watertight": True,
                "volume_cm3": round(float(piece.mesh.volume) / 1000.0, 3),
                "bounds_mm": [
                    [round(float(value), 4) for value in row]
                    for row in piece.mesh.bounds
                ],
            }
        )
    return component_dir, records


def write_obj(pieces: list[assembly.Piece], out_dir: Path) -> tuple[Path, Path]:
    scene = trimesh.Scene()
    for index, piece in enumerate(pieces):
        name = PART_STEMS[piece.label]
        mesh = piece.mesh.copy()
        # Give each object its own material slot, even when colours match.
        # Some OBJ importers merge objects that share a material; unique slots
        # preserve all nine lamp bodies in Fusion's Browser.
        mesh.visual = TextureVisuals(
            material=SimpleMaterial(
                name=name,
                diffuse=piece.colour,
                glossiness=1.0 + index * 0.01,
            )
        )
        scene.add_geometry(mesh, node_name=name, geom_name=name)

    obj_text, resources = export_obj(
        scene,
        include_normals=True,
        include_color=False,
        include_texture=True,
        return_texture=True,
        write_texture=True,
        digits=10,
        mtl_name=MTL_NAME,
        header=(
            "Bouclé Stack lamp Autodesk Fusion assembly; "
            "units are millimetres; meshes are already assembled"
        ),
    )
    obj_path = out_dir / OBJ_NAME
    obj_path.write_text(obj_text, encoding="utf-8")
    mtl_payload = resources.get(MTL_NAME)
    if mtl_payload is None:
        raise RuntimeError("OBJ exporter did not produce its material library")
    mtl_path = out_dir / MTL_NAME
    if isinstance(mtl_payload, str):
        mtl_path.write_text(mtl_payload, encoding="utf-8")
    else:
        mtl_path.write_bytes(mtl_payload)

    object_names = {
        line[2:].strip()
        for line in obj_text.splitlines()
        if line.startswith("o ")
    }
    if object_names != set(PART_STEMS.values()):
        raise RuntimeError(
            f"OBJ object names are incomplete: {sorted(object_names)}"
        )
    return obj_path, mtl_path


def fusion_script(part_records: list[dict]) -> str:
    rows = ",\n".join(
        f'    ({record["name"]!r}, {record["file"]!r})'
        for record in part_records
    )
    return f'''"""Import the Bouclé Stack package as named Fusion mesh components."""

import traceback
from pathlib import Path

import adsk.core
import adsk.fusion


PARTS = [
{rows}
]


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if design is None:
            app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
            design = adsk.fusion.Design.cast(app.activeProduct)
        if design is None:
            raise RuntimeError("Open or create a Fusion Design before importing.")

        package_root = Path(__file__).resolve().parent.parent
        root = design.rootComponent
        imported = 0
        for part_name, relative_path in PARTS:
            source = package_root / relative_path
            if not source.exists():
                raise FileNotFoundError(source)

            occurrence = root.occurrences.addNewComponent(
                adsk.core.Matrix3D.create()
            )
            occurrence.name = part_name
            component = occurrence.component
            component.name = part_name

            base_feature = component.features.baseFeatures.add()
            base_feature.name = f"{{part_name}} mesh import"
            base_feature.startEdit()
            try:
                mesh_bodies = component.meshBodies.add(
                    str(source),
                    adsk.fusion.MeshUnits.MillimeterMeshUnit,
                    base_feature,
                )
            finally:
                base_feature.finishEdit()
            if mesh_bodies is None or mesh_bodies.count == 0:
                raise RuntimeError(f"Fusion did not import {{part_name}}")
            for index in range(mesh_bodies.count):
                mesh_bodies.item(index).name = part_name
            imported += 1

        app.activeViewport.fit()
        ui.messageBox(
            f"Imported {{imported}} Bouclé Stack mesh components in millimetres."
        )
    except Exception:
        ui.messageBox(
            "Bouclé Stack import failed:\\n\\n" + traceback.format_exc()
        )
'''


def write_fusion_script(part_records: list[dict], out_dir: Path) -> Path:
    script_dir = out_dir / SCRIPT_DIR_NAME
    script_dir.mkdir(parents=True, exist_ok=True)
    script_path = script_dir / f"{SCRIPT_DIR_NAME}.py"
    script_path.write_text(fusion_script(part_records), encoding="utf-8")
    manifest = {
        "autodeskProduct": "Fusion360",
        "type": "script",
        "author": "Ogma Print",
        "description": {
            "": (
                "Import the complete Bouclé Stack lamp as nine named mesh "
                "components in their finished assembly positions."
            )
        },
        "version": "1.0.0",
        "supportedOS": "windows|mac",
        "editEnabled": True,
    }
    (script_dir / f"{SCRIPT_DIR_NAME}.manifest").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return script_dir


def readme_text() -> str:
    return """# Bouclé Stack lamp — Autodesk Fusion mesh package

This package contains the complete production-resolution lamp in its finished
assembly position. Units are **millimetres** and the assembly origin is the
centre of the leg-frame base.

## Recommended import: named Fusion components

1. Unzip the package and keep its folder structure intact.
2. In Fusion, open **Utilities → Scripts and Add-Ins**.
3. Click the green **+**, select the `FusionImportBoucleStack/` folder, then run
   `FusionImportBoucleStack`.
4. The script creates nine named components: the eight printable parts plus an
   LED-module reference body.

## Manual alternatives

- **OBJ:** Mesh → Create → Insert Mesh, select
  `Boucle_Stack_Lamp_Fusion_Assembly.obj`, choose **Millimeter**, and leave
  position/rotation at zero. Keep the adjacent `.mtl` file for colours. The OBJ
  contains nine separately named mesh objects.
- **3MF:** Insert `Boucle_Stack_Lamp_Fusion_Assembly.3mf`. Its units are embedded
  and all bodies are already assembled at the origin.
- **Individual components:** Import any files under `components/` in
  millimetres. Every OBJ is already in its finished world position.

## Important limitations

- These are exact watertight **mesh bodies**, not a native parametric `.f3d` or
  analytic STEP model. The source design is generated through mesh booleans.
- Autodesk advises reducing meshes above roughly 10,000 facets before B-Rep
  conversion. Several exact lamp parts exceed that threshold; use them as
  reference meshes or reduce/remodel one component at a time.
- Fuzzy skin is generated by Bambu Studio while slicing. Fusion will show the
  shells as smooth CAD meshes. The production project uses the proven Classic
  texture at 0.30 mm thickness and 0.80 mm point distance.
- The assembled exports are not print layouts. Continue printing from the
  eight-plate P2S production 3MF.
"""


def write_zip(out_dir: Path, paths: list[Path]) -> Path:
    zip_path = out_dir / ZIP_NAME
    with zipfile.ZipFile(
        zip_path,
        "w",
        zipfile.ZIP_DEFLATED,
        compresslevel=7,
    ) as package:
        for path in paths:
            if path == zip_path:
                continue
            if path.is_dir():
                for child in sorted(path.rglob("*")):
                    if child.is_file():
                        package.write(child, child.relative_to(out_dir))
            else:
                package.write(path, path.relative_to(out_dir))
    with zipfile.ZipFile(zip_path) as package:
        if package.testzip() is not None:
            raise RuntimeError("Fusion package ZIP failed its CRC check")
    return zip_path


def generate(out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pieces, report = exact_assembly()
    component_dir, part_records = write_components(pieces, out_dir)
    obj_path, mtl_path = write_obj(pieces, out_dir)
    script_dir = write_fusion_script(part_records, out_dir)

    palette = load_palette()
    three_mf = assembly.write_project(
        pieces,
        out_dir,
        resolve_filament(coupons.SHELL_FILAMENT, palette).hex,
        resolve_filament(coupons.BASE_FILAMENT, palette).hex,
        output_name=THREE_MF_NAME,
        title="Bouclé Stack lamp — Autodesk Fusion mesh assembly",
        include_reference=True,
        build_offset=(0.0, 0.0, 0.0),
    )

    combined = trimesh.util.concatenate([piece.mesh for piece in pieces])
    report["fusion_export"] = {
        "format": "componentized exact mesh assembly",
        "units": "mm",
        "origin": "centre of leg-frame base",
        "printed_component_count": sum(piece.printed for piece in pieces),
        "reference_component_count": sum(not piece.printed for piece in pieces),
        "total_triangle_count": sum(len(piece.mesh.faces) for piece in pieces),
        "overall_bounds_mm": [
            [round(float(value), 4) for value in row]
            for row in combined.bounds
        ],
        "files": {
            "obj": OBJ_NAME,
            "mtl": MTL_NAME,
            "3mf": THREE_MF_NAME,
            "components": "components/",
            "fusion_script": f"{SCRIPT_DIR_NAME}/",
        },
        "fuzzy_skin_geometry": False,
        "fuzzy_skin_note": (
            "Production Classic fuzzy skin remains slicer metadata and is "
            "not tessellated into the Fusion meshes."
        ),
        "parts": part_records,
    }
    manifest_path = out_dir / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    readme_path = out_dir / README_NAME
    readme_path.write_text(readme_text(), encoding="utf-8")

    zip_path = write_zip(
        out_dir,
        [
            obj_path,
            mtl_path,
            three_mf,
            component_dir,
            script_dir,
            manifest_path,
            readme_path,
        ],
    )
    return {
        "zip": zip_path,
        "obj": obj_path,
        "3mf": three_mf,
        "manifest": manifest_path,
        "readme": readme_path,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    for kind, path in generate(args.out).items():
        print(f"{kind:8} {path}")
