"""Import the Bouclé Stack package as named Fusion mesh components."""

import traceback
from pathlib import Path

import adsk.core
import adsk.fusion


PARTS = [
    ('Leg frame', 'components/01_Leg_Frame.obj'),
    ('LED cradle', 'components/02_LED_Cradle.obj'),
    ('Diffuser baffle', 'components/03_Diffuser_Baffle.obj'),
    ('Shell A', 'components/04_Shell_A.obj'),
    ('Halo ring A–B', 'components/05_Halo_Ring_A_to_B.obj'),
    ('Shell B', 'components/06_Shell_B.obj'),
    ('Halo ring B–C', 'components/07_Halo_Ring_B_to_C.obj'),
    ('Shell C', 'components/08_Shell_C.obj'),
    ('LED module (reference)', 'components/09_LED_Module_Reference.obj')
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
            base_feature.name = f"{part_name} mesh import"
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
                raise RuntimeError(f"Fusion did not import {part_name}")
            for index in range(mesh_bodies.count):
                mesh_bodies.item(index).name = part_name
            imported += 1

        app.activeViewport.fit()
        ui.messageBox(
            f"Imported {imported} Bouclé Stack mesh components in millimetres."
        )
    except Exception:
        ui.messageBox(
            "Bouclé Stack import failed:\n\n" + traceback.format_exc()
        )
