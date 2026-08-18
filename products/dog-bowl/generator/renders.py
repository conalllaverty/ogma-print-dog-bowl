"""Photoreal stills of the finished stand, written alongside the 3MF.

The generator already writes every part twice — flat for printing, and once
positioned in the finished assembly as `assembly_<part>.stl`. That second set is
the product as the customer will own it, and until now nothing looked at it
outside the browser preview. This renders it.

The colours are the customer's actual filament choices, so the pictures in the
download are of the thing that was ordered rather than of a generic example.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import trimesh

import cooper_bowl_design as design
from ogma import preview as preview_lib
from ogma import render as render_lib

from preview import role_for

log = logging.getLogger("dogbowl.renders")

# The stainless bowl is not a filament and is never configurable — it is the
# off-the-shelf part the stand is built around. Same value the web viewer uses.
#
# A mid grey, not the near-white it used to be. #C9CCD1 is roughly the colour a
# steel bowl *looks* in a bright showroom photo, which is already the result of
# lighting — feeding it back in as base colour double-counts the exposure and
# the bowl blows out. The base colour should be the material, and the lights
# should do the lifting.
BOWL_HEX = "#9AA1A9"

RENDER_DIRNAME = "renders"


def build(
    job_dir: Path,
    *,
    stand_hex: str,
    letter_hex: str,
    upper_hex: str | None = None,
    letters_enabled: bool = True,
    width: int = 1600,
    height: int = 1200,
    timeout: float = 300.0,
) -> list[str]:
    """Render the assembled stand into `job_dir/renders`, in a child process.

    **The subprocess is the point, not an implementation detail.**

    Jobs run on a worker thread (studio/api/services/jobs.py starts one per
    job), and creating an OpenGL context off the main thread is not allowed on
    macOS: pyglet's CGL backend touches NSApplication's main menu, and AppKit
    answers with an uncaught `NSInternalInconsistencyException` — *API misuse:
    setting the main menu on a non-main thread*. That is not an exception this
    code can catch. It calls `abort()`, and the entire API process dies with the
    customer's job still running.

    In a child process the render happens on that process's main thread, which
    satisfies AppKit. It also contains the failure everywhere else: a GL driver
    that segfaults in a headless container now costs one set of pictures rather
    than the server.

    Returns an empty list rather than raising if rendering is unavailable. The
    printable output is the deliverable, and a machine with no GL stack must
    still be able to produce one.
    """
    job_dir = Path(job_dir)
    argv = [
        sys.executable,
        str(Path(__file__).resolve()),
        str(job_dir),
        "--stand", stand_hex,
        "--letters", letter_hex,
        "--upper", upper_hex or stand_hex,
        "--width", str(width),
        "--height", str(height),
    ]
    if not letters_enabled:
        argv.append("--no-letters")

    env = dict(os.environ)
    # The child gets the same import roots this module was found through, so it
    # does not depend on how the parent happened to be launched.
    generator_dir = Path(__file__).resolve().parent
    repo = next(p for p in generator_dir.parents if (p / "shared" / "ogma").is_dir())
    env["PYTHONPATH"] = os.pathsep.join(
        [str(generator_dir), str(repo / "shared"), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)

    try:
        done = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, env=env
        )
    except subprocess.TimeoutExpired:
        log.warning("render timed out after %.0fs — continuing without images", timeout)
        return []

    if done.returncode != 0:
        # Includes the abort()-style deaths a try/except could never see.
        log.warning(
            "render subprocess exited %s — continuing without images\n%s",
            done.returncode,
            (done.stderr or "")[-800:],
        )
        return []

    # The last line, not the whole stream: GL drivers and pyglet are entitled to
    # write to stdout, and a single stray banner would otherwise throw away a
    # perfectly good set of renders.
    tail = [ln for ln in (done.stdout or "").splitlines() if ln.strip()]
    try:
        return json.loads(tail[-1])
    except (IndexError, json.JSONDecodeError):
        log.warning("render subprocess produced no file list: %r", done.stdout[-300:])
        return []


def render_here(
    job_dir: Path,
    *,
    stand_hex: str,
    letter_hex: str,
    upper_hex: str | None = None,
    letters_enabled: bool = True,
    width: int = 1600,
    height: int = 1200,
) -> list[str]:
    """Do the actual render, in this process. Called by `build`'s child.

    Not for use from a server thread — see `build` for why.
    """
    job_dir = Path(job_dir)
    mesh_dir = job_dir / "meshes"

    # `stand_upper` is the split wave's upper shell and seat insert. On a
    # single-body style nothing carries that role, so the fallback is never
    # reached — but defaulting it to the stand keeps this total.
    colours = {
        "stand": stand_hex,
        "stand_upper": upper_hex or stand_hex,
        "letters": letter_hex,
        "bowl": BOWL_HEX,
    }

    parts: list[render_lib.Part] = []
    have_bowl = False
    for path in preview_lib.assembled_meshes(mesh_dir):
        role = role_for(path.name)
        # A design without glue-in letters has letter meshes on disk — they are
        # built to cut the pockets — but they are not part of what ships.
        if role == "letters" and not letters_enabled:
            continue
        have_bowl = have_bowl or role == "bowl"
        parts.append(
            render_lib.Part(
                role=role, mesh=trimesh.load_mesh(path), colour=colours[role]
            )
        )

    if not have_bowl:
        # Only the paw lattice exports the reference bowl as a mesh. Every style
        # seats the same one, and a stand photographed without its bowl reads as
        # an empty ring — see the same fallback in this product's preview.py.
        parts.append(
            render_lib.Part(role="bowl", mesh=design.visual_bowl(), colour=BOWL_HEX)
        )

    if not parts:
        log.warning("no assembled meshes in %s — nothing to render", mesh_dir)
        return []

    written = render_lib.render(
        parts, job_dir / RENDER_DIRNAME, width=width, height=height
    )
    return [p.name for p in written]


if __name__ == "__main__":
    import argparse

    # This entry point is what `build` spawns, so it calls `render_here`, not
    # `build` — the latter would fork a child of the child, forever.
    ap = argparse.ArgumentParser(description="Render an existing job's assembly")
    ap.add_argument("job_dir", type=Path)
    ap.add_argument("--stand", default="#757575")
    ap.add_argument("--letters", default="#FFFFFF")
    ap.add_argument("--upper", default=None)
    ap.add_argument("--no-letters", action="store_true")
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--height", type=int, default=1200)
    a = ap.parse_args()
    # stdout is the child's return channel and must carry nothing but the JSON.
    print(
        json.dumps(
            render_here(
                a.job_dir,
                stand_hex=a.stand,
                letter_hex=a.letters,
                upper_hex=a.upper,
                letters_enabled=not a.no_letters,
                width=a.width,
                height=a.height,
            )
        )
    )
