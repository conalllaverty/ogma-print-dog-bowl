"""Photoreal stills of an assembled product, rendered from the printed meshes.

Why this exists: the customer buys an object, and every picture we had of it was
either a plate layout (three rings on a build plate, which reads as parts, not a
product) or the live WebGL viewer (which only exists while someone has the
designer open). This renders the *assembled* thing, offline, as part of the job
— so a download can contain pictures of what was bought.

Product-agnostic by rule, like the rest of `shared/ogma`: it is handed a list of
`Part`s with roles and colours and knows nothing about bowls.

Two things carry most of the realism, and neither is the material model:

1. **Supersampling.** Rendered at SS× the output size and Lanczos-downsampled.
   A rasteriser with no AA puts a stair-stepped edge on every silhouette, and on
   a smooth turned object that single artifact reads as "3D render" louder than
   any amount of shading work.

2. **Three-point light with a real shadow.** pyrender has no image-based
   lighting, so a single light gives the flat, origin-less look of a clay
   render. A broad key with a directional shadow map, a fill at a quarter of its
   strength to keep the dark side readable, and a rim behind to separate the
   object from the backdrop is the standard studio answer, and it is what makes
   matte PLA look like a photographed object.

The backdrop is a seamless sweep — a large ground plane, with the background
colour matched to it — so there is no visible horizon line behind the product.
"""

from __future__ import annotations

import logging
import math
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

log = logging.getLogger("ogma.render")


def _select_gl_backend() -> None:
    """Pick an offscreen GL backend before pyrender/PyOpenGL are imported.

    This has to happen at import time and it has to be conditional. macOS has
    neither EGL nor OSMesa and renders offscreen through pyglet's CGL context;
    Linux containers have no display and must use EGL. Setting `PYOPENGL_PLATFORM
    = egl` unconditionally — which is what products/dog-bowl/tools does — fails
    on a developer's Mac with `Unable to load EGL library`, and leaving it unset
    fails in the container with `Unable to open display`.

    Respects an existing value, so a deployment can force OSMesa without editing
    this.
    """
    if os.environ.get("PYOPENGL_PLATFORM"):
        return
    if platform.system() != "Darwin":
        os.environ["PYOPENGL_PLATFORM"] = "egl"


_select_gl_backend()

# pyrender 0.1.45 is the last release (2019) and predates NumPy 2, which removed
# the `np.infty` alias. `pyrender/mesh.py` still uses it to seed an empty
# bounding box, which is reached the moment a light needs a shadow camera — so
# rendering works until you ask for shadows, then dies with an AttributeError
# from inside a dependency.
#
# Restoring the alias is the whole fix, and it is the same object the name
# always referred to. Scoped to this import rather than done globally, and
# conditional so it disappears by itself if pyrender is ever updated.
if not hasattr(np, "infty"):  # pragma: no cover - environment shim
    np.infty = np.inf  # type: ignore[attr-defined]

import pyrender  # noqa: E402
import trimesh  # noqa: E402
from PIL import Image  # noqa: E402


# Supersampling factor. 2 is the knee of the curve — 3 is visibly better than 1
# and barely distinguishable from 2 at these output sizes, for 2.25× the pixels.
SUPERSAMPLE = 2

# Studio sweep. Deliberately not white: a light warm grey keeps the ivory
# letters from clipping against the background, which is the one value pairing
# in the palette that can vanish.
BACKDROP = (0.129, 0.125, 0.122)



@dataclass(frozen=True)
class Part:
    """One printed component, ready to render."""

    role: str
    mesh: trimesh.Trimesh
    #: sRGB hex, as chosen by the customer ("#AE835B").
    colour: str


@dataclass(frozen=True)
class View:
    """One camera setup.

    Angles are degrees. `margin` is headroom around the object as a multiple of
    the distance that exactly fills the frame — the distance itself is computed
    from the model's bounding sphere, not hand-tuned, because a fixed multiple of
    "model size" silently crops as soon as a name gets longer or a style gets
    taller. It did: at 2.05× the paw lattice ran off both edges of the frame.
    """

    name: str
    azimuth: float
    elevation: float
    margin: float = 1.08
    fov_deg: float = 26.0


# The four a customer actually wants: the hero shot they will recognise the
# product from, a square-on front that shows the name at its most legible, a
# profile that shows the wall pattern without perspective foreshortening, and a
# top-down that answers "how deep is the bowl".
DEFAULT_VIEWS = (
    View("hero", azimuth=-38.0, elevation=22.0),
    View("front", azimuth=0.0, elevation=8.0),
    View("side", azimuth=-90.0, elevation=12.0),
    View("top", azimuth=-30.0, elevation=62.0, margin=1.14),
)


def _srgb_to_linear(hex_colour: str) -> list[float]:
    """Hex to linear-light RGB.

    pyrender's `baseColorFactor` is linear, and the palette hexes are sRGB.
    Feeding sRGB straight in is the single most common reason a render comes out
    washed out and chalky: a mid grey lands about 30% too bright.
    """
    h = hex_colour.lstrip("#")
    srgb = [int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return [
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb
    ]


# Above this dihedral an edge is a real edge and shades hard; below it the faces
# are approximating a curve and shade as one. Matches CREASE_ANGLE in
# studio/web/src/components/Viewer.tsx — the still and the live preview must
# describe one object, and this is the number that decides how it is shaded.
CREASE_ANGLE_DEG = 12.0


def creased_normals(
    mesh: trimesh.Trimesh, crease_deg: float = CREASE_ANGLE_DEG
) -> trimesh.Trimesh:
    """Per-corner normals that stop at creases. three.js's `toCreasedNormals`.

    Replaces an earlier fix that subdivided long edges instead. Both target the
    same artifact — the vertical bands hanging below every paw — but this one is
    free and that one was not.

    The artifact: cutting 16 paw recesses into the wall leaves the untouched part
    of that wall retriangulated into slivers ~1 mm wide and up to 24 mm tall. The
    geometry is exact (still a cylinder to within 0.01 mm), but plain area-
    weighted vertex normals average the recess rim into the wall, and that tilt
    then interpolates down the whole length of a sliver.

    Subdividing bounds how far the tilt can travel; refusing to average across
    the rim stops it happening at all. Measured on the paw panel, as deviation of
    the shading normal from true radial on the clean wall below the pads:
    9.8° max at 25°, 1.0° at 12° — and 1.0° is the cylinder's own faceting, i.e.
    the floor. Subdividing to reach the same place cost 7× the triangles.

    Returns a non-indexed mesh, because a vertex on a crease needs a different
    normal for each side of it — which is exactly why this cannot be expressed as
    one normal per shared vertex.
    """
    from collections import defaultdict

    v = np.asarray(mesh.vertices)
    f = np.asarray(mesh.faces)
    face_n = np.asarray(mesh.face_normals)
    face_a = np.asarray(mesh.area_faces)
    threshold = math.cos(math.radians(crease_deg))

    incident: dict[int, list[int]] = defaultdict(list)
    for face_index, tri in enumerate(f):
        for vertex in tri:
            incident[int(vertex)].append(face_index)

    out = np.empty((len(f), 3, 3), dtype=np.float64)
    for face_index in range(len(f)):
        own = face_n[face_index]
        for corner, vertex in enumerate(f[face_index]):
            # Area-weighted, and only over faces on this side of the crease.
            neighbours = [
                j for j in incident[int(vertex)] if float(face_n[j] @ own) >= threshold
            ]
            summed = (face_n[neighbours] * face_a[neighbours][:, None]).sum(axis=0)
            length = float(np.linalg.norm(summed))
            out[face_index, corner] = own if length < 1e-12 else summed / length

    flat = trimesh.Trimesh(
        vertices=v[f].reshape(-1, 3),
        faces=np.arange(len(f) * 3).reshape(-1, 3),
        process=False,
    )
    flat.vertex_normals = out.reshape(-1, 3)
    return flat


def _grade(rgb: np.ndarray) -> np.ndarray:
    """Camera-side finishing: bloom, an S-curve, and a vignette.

    A rasteriser hands back exactly the light it computed, and nothing in that
    chain does what a lens and a sensor do. These three are the cheapest steps
    that read as "photographed" rather than "rendered", and none of them changes
    what the object *is*:

    - **Bloom** — bright highlights bleeding into their surroundings. The one
      cue that says a real highlight was too bright for the sensor. Taken from
      the top of the range only, so matte PLA is untouched and the stainless
      bowl's specular gets it.
    - **S-curve** — film's toe and shoulder. Deepens the shadows and rolls off
      the highlights instead of clipping them flat.
    - **Vignette** — very slight. Holds the eye on the product, and separates a
      light backdrop from the frame edge.

    Applied after downsampling, so the blur radius is in output pixels and does
    not silently change with the supersampling factor.
    """
    from PIL import ImageFilter

    x = rgb.astype(np.float32) / 255.0

    # Bloom. Isolate what is near the top of the range, blur it, add it back.
    luminance = x.max(axis=2)
    weight = np.clip((luminance - 0.88) / 0.12, 0.0, 1.0)[..., None]
    highlights = Image.fromarray((x * weight * 255.0).astype(np.uint8))
    blurred = np.asarray(
        highlights.filter(ImageFilter.GaussianBlur(radius=8))
    ).astype(np.float32) / 255.0
    x = x + blurred * 0.16

    # Mid lift, then mild contrast about mid grey.
    #
    # Deliberately gentle and in this order. A film-style S-curve applied to an
    # already display-referred image is not a tone map, it is just a crush: the
    # first attempt here darkened a lit product into a silhouette. The gamma
    # opens the mid-tones the ambient fill lives in; the contrast is small
    # enough to keep the shadow detail in the paw recesses.
    x = np.clip(x, 0.0, 1.0) ** 0.97
    x = np.clip(0.5 + (x - 0.5) * 1.08, 0.0, 1.0)

    # Vignette.
    h, w = x.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    radius = np.hypot(
        (xx - w / 2.0) / (w / 2.0), (yy - h / 2.0) / (h / 2.0)
    ) / math.sqrt(2.0)
    x *= (1.0 - 0.20 * radius**2.2)[..., None]

    return np.clip(x, 0.0, 1.0)


def _material(part: Part) -> pyrender.MetallicRoughnessMaterial:
    """Matte PLA, or brushed stainless for the bowl.

    These numbers were once described here as "the same ones
    studio/web/src/components/Viewer.tsx uses, so the still and the live preview
    describe one object rather than two". They were not the same, and nothing
    checked: the viewer's bowl was running metalness 0.82 / roughness 0.46
    against the 0.60 / 0.70 below, and 41.6% of its bowl interior clipped to
    white while this renderer's clipped 0.0%.

    They are still not the same, and now deliberately. pyrender lights this scene
    with four analytic lights and no environment; three.js adds an image-based
    probe on top of a comparable rig. For a metal — whose base colour *is* its
    specular colour — the same constants therefore land brighter over there, and
    the viewer needs a rougher, darker bowl to arrive at the same picture. Two
    engines agreeing on a number is not the goal; two engines agreeing on an
    image is.
    """
    if part.role == "bowl":
        # Brushed stainless, and deliberately far rougher / less metallic than
        # the physical truth.
        #
        # A near-mirror metal has almost no diffuse term, so with no environment
        # map it can only reflect the four analytic lights. Worse, the bowl's
        # floor is *flat* and the key is *directional*: every point on it meets
        # the specular condition at the same moment, so the whole floor hits the
        # highlight together and clips as one white pool. It measured 4.7% of
        # bowl pixels at or above 250.
        #
        # Roughness is the lever that fixes it, not metalness — it spreads the
        # lobe so the floor shades as a gradient instead of a switch. At 0.70
        # with a mid-grey base the clipping is 0.0% and the bowl reads as
        # brushed steel rather than as a blown-out disc.
        return pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[*_srgb_to_linear(part.colour), 1.0],
            metallicFactor=0.60,
            roughnessFactor=0.70,
        )
    return pyrender.MetallicRoughnessMaterial(
        baseColorFactor=[*_srgb_to_linear(part.colour), 1.0],
        metallicFactor=0.0,
        # Matte PLA is genuinely rough. Below ~0.6 it starts reading as satin,
        # which is the wrong product.
        roughnessFactor=0.78,
    )


def _look_at(eye: np.ndarray, target: np.ndarray, up=(0.0, 0.0, 1.0)) -> np.ndarray:
    """Camera-to-world pose in OpenGL convention (camera looks down its own -Z)."""
    eye = np.asarray(eye, float)
    target = np.asarray(target, float)
    forward = target - eye
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, np.asarray(up, float))
    right /= np.linalg.norm(right)
    true_up = np.cross(right, forward)
    pose = np.eye(4)
    pose[:3, 0] = right
    pose[:3, 1] = true_up
    pose[:3, 2] = -forward
    pose[:3, 3] = eye
    return pose


def _add_lights(scene: pyrender.Scene, centre: np.ndarray, extent: float) -> None:
    """Key, fill and rim, all directional so intensity is scale-independent.

    Directional rather than point: a point light's falloff is inverse-square in
    scene units, and this scene is in millimetres, so a point light bright
    enough for a 170 mm object needs an intensity in the tens of thousands and
    becomes wildly sensitive to the object's size. Directional light has no
    falloff, so the same three numbers light any product this module is given.
    """
    distance = extent * 3.0

    def place(azimuth_deg: float, elevation_deg: float) -> np.ndarray:
        az, el = math.radians(azimuth_deg), math.radians(elevation_deg)
        offset = np.array(
            [
                math.cos(el) * math.sin(az),
                -math.cos(el) * math.cos(az),
                math.sin(el),
            ]
        )
        return _look_at(centre + offset * distance, centre)

    # Intensities calibrated against Bambu Lab's own product photography, not
    # by eye. Sampling their Matte Dark Red vase gives a median of #882F31 at
    # 0.65 saturation; the same filament rendered here now lands at #872D30 and
    # 0.66 — a distance of 1.1 in RGB. The earlier, brighter rig came out at
    # #A1373B, a distance of 28.8, and read as pink.
    #
    # Checked across the palette's range before committing, because tuning on
    # one dark colour is how you crush every other: Ivory White still means
    # luminance 160 with a 95th percentile of 195, and Charcoal gains 0.2
    # percentage points of near-black pixels. Nothing clips at either end.
    #
    # ---- exactly four, because four is all there are ----------------------
    # pyrender's MAX_N_LIGHTS is 4, and it enforces it *silently*: extra lights
    # are dropped, nearest-first, with no warning. A twelve-light dome
    # approximating image-based lighting — which is what the live preview gets
    # from three.js's RoomEnvironment probe, and the reason it looks softer than
    # these stills — is therefore not available here. Raising the constant does
    # not help either: with SHADOWS_DIRECTIONAL every directional light also
    # wants a shadow-map texture unit, and the renderer clamps the count back
    # down to what the GL context has spare.
    #
    # So the wraparound has to come from `ambient_light` (set by the caller) and
    # from spending all four lights well, rather than from more of them.

    # Key: high and to the left. The only one that casts the shadow — two
    # crossing shadows read as a stage set, not a photograph.
    scene.add(pyrender.DirectionalLight(color=[1.0, 0.97, 0.93], intensity=2.2),
              pose=place(-46.0, 44.0))
    # Fill: opposite and low, about a third of key. Cool, because a bounce off a
    # neutral surround is, and the warm/cool split is most of what stops a
    # two-light render looking like plastic.
    scene.add(pyrender.DirectionalLight(color=[0.86, 0.91, 1.0], intensity=0.55),
              pose=place(58.0, 14.0))
    # Rim: behind and high, drawing a bright edge along the silhouette.
    scene.add(pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=1.00),
              pose=place(158.0, 40.0))
    # Bounce: from below the horizon, very weak and warm — the floor throwing
    # light back up into the overhangs. Without it the underside of the rim and
    # the inside of the base go to flat shadow.
    scene.add(pyrender.DirectionalLight(color=[1.0, 0.93, 0.85], intensity=0.25),
              pose=place(-10.0, -28.0))


def _ground(centre: np.ndarray, z_min: float, extent: float) -> trimesh.Trimesh:
    """A disc for the product to sit on and cast its contact shadow onto.

    Sized deliberately, not generously. pyrender fits the directional shadow
    camera to the whole scene's bounds, so a floor far larger than the frame
    spreads a fixed-resolution depth buffer over an area that is mostly empty
    ground, leaving too little precision for the product to tell its own surface
    from itself. That is shadow acne, and at 4× it appeared as diagonal hatching
    across the name plaque and the upper wall.

    3.2× is the measured compromise. The disc's edge sits outside the frame at
    every default view, so the floor meets the background as a straight horizon
    high in the shot instead of as a visible ellipse, and the shadow map stays
    tight enough to be clean.
    """
    ground = trimesh.creation.cylinder(radius=extent * 3.2, height=extent * 0.02)
    ground.apply_translation([centre[0], centre[1], z_min - extent * 0.01])
    return ground


def render(
    parts: Sequence[Part],
    out_dir: Path,
    *,
    views: Sequence[View] = DEFAULT_VIEWS,
    width: int = 1600,
    height: int = 1200,
    basename: str = "assembled",
) -> list[Path]:
    """Render `parts` from each view. Returns the PNGs written, in view order.

    Never raises for rendering reasons: a job that has produced a printable 3MF
    must not fail because a machine has no GL. The caller gets a shorter list
    (possibly empty) and a warning in the log.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    scene = pyrender.Scene(
        bg_color=[*BACKDROP, 1.0],
        # Low, not zero: pure three-point light leaves the deepest recesses at
        # true black, and a paw pad that reads as a hole is worse than one a
        # little lifted.
        # Low, and deliberately so. Ambient is *neutral* light, so every unit of
        # it dilutes the filament's own hue — a saturated colour lit with a lot
        # of white fill drifts toward pastel. Dark Red measured a saturation of
        # 0.67 as a hex and rendered at 0.52 in the browser, which is exactly
        # that effect. See _add_lights for the values this trades against.
        ambient_light=[0.04, 0.04, 0.043],
    )

    bounds = np.vstack([p.mesh.bounds for p in parts])
    lo, hi = bounds.min(axis=0), bounds.max(axis=0)
    centre = (lo + hi) / 2.0
    extent = float(np.max(hi - lo))
    # Bounding-sphere radius: the framing has to hold the object at any azimuth,
    # and the diagonal is the only measure that does.
    sphere_r = float(np.linalg.norm(hi - lo)) / 2.0

    for part in parts:
        scene.add(
            pyrender.Mesh.from_trimesh(
                creased_normals(part.mesh), material=_material(part), smooth=True
            ),
            name=f"{part.role}",
        )

    ground = _ground(centre, float(lo[2]), extent)
    scene.add(
        pyrender.Mesh.from_trimesh(
            ground,
            material=pyrender.MetallicRoughnessMaterial(
                baseColorFactor=[*BACKDROP, 1.0],
                metallicFactor=0.0,
                roughnessFactor=0.95,
            ),
            smooth=False,
        ),
        name="backdrop",
    )
    _add_lights(scene, centre, extent)

    rw, rh = width * SUPERSAMPLE, height * SUPERSAMPLE
    written: list[Path] = []
    renderer = None
    try:
        renderer = pyrender.OffscreenRenderer(rw, rh)
        for view in views:
            az, el = math.radians(view.azimuth), math.radians(view.elevation)
            fov = math.radians(view.fov_deg)
            # Distance at which the bounding sphere exactly fills the vertical
            # field, times the view's margin.
            distance = sphere_r / math.sin(fov / 2.0) * view.margin
            eye = centre + np.array(
                [
                    math.cos(el) * math.sin(az),
                    -math.cos(el) * math.cos(az),
                    math.sin(el),
                ]
            ) * distance
            # Near and far planes fitted to the scene, not left at pyrender's
            # defaults.
            #
            # The default znear is 0.05, which is fine for a scene measured in
            # metres and ruinous for one measured in millimetres: with the
            # camera ~600 mm out, the depth buffer spends almost all of its
            # precision in the first millimetre and has close to none left where
            # the object actually is. Coincident surfaces then flicker — the
            # stainless bowl and the seat ring it sits in speckled red along the
            # rim, which reads as dirt on the bowl.
            #
            # Fitting the planes to the model brings the far/near ratio from
            # ~30,000 down to about 12, which is ample.
            znear = max(1.0, distance * 0.2)
            zfar = distance + extent * 5.0
            camera = pyrender.PerspectiveCamera(
                yfov=fov, aspectRatio=rw / rh, znear=znear, zfar=zfar
            )
            node = scene.add(camera, pose=_look_at(eye, centre))
            try:
                colour, _ = renderer.render(
                    scene,
                    flags=pyrender.RenderFlags.SHADOWS_DIRECTIONAL,
                )
            finally:
                scene.remove_node(node)

            path = out_dir / f"{basename}_{view.name}.png"
            downsampled = np.asarray(
                Image.fromarray(colour).resize((width, height), Image.LANCZOS)
            )
            Image.fromarray((_grade(downsampled) * 255.0).astype(np.uint8)).save(
                path, optimize=True
            )
            written.append(path)
    except Exception as exc:  # noqa: BLE001
        log.warning("render unavailable (%s: %s)", type(exc).__name__, exc)
    finally:
        if renderer is not None:
            try:
                renderer.delete()
            except Exception:  # noqa: BLE001
                pass
    return written
