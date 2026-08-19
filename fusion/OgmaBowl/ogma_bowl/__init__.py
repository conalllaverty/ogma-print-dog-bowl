"""Ogma dog-bowl parametric builders for Autodesk Fusion.

The package is a translation of products/dog-bowl/generator/ from trimesh mesh
operations into Fusion BRep features, so that the same four styles exist as
editable, parameter-driven models rather than as exported meshes.

Layout
    config.py   transcribed geometry constants, checked against the generator
    units.py    the one place mm <-> Fusion's internal cm conversion happens
    api.py      thin wrappers over the Fusion calls, current signatures only
    params.py   User Parameters — the editable control surface
    letters.py  the name: pockets in the wall, and the glue-in letter solids
    styles/     one module per bowl style, same registry shape as the generator
    build.py    orchestration, shared by the toolbar command and the exporter
"""

__version__ = "1.0.0"
