"""The paw wall's fuzzy skin: what gets painted, and in whose coordinates.

Two things are locked in here, both of which shipped wrong at some point and
neither of which anything else covers:

**The paws themselves must stay smooth.** Fuzzy skin on a pad flank is a
cleaning problem — the texture is exactly where food gets into — and it blunts
the paw outline that is the whole point of the style.

**The mask has to be in the same frame as the mesh.** The pad silhouettes are
specified in assembly coordinates and the mask is usually handed a mesh in
print orientation, so the two must be reconciled. Get that wrong and the
exclusions land on blank wall while the pads get fuzzed through. That is not
hypothetical: the one-piece stand shipped with 59.8% of its pads painted,
because every assertion at the time recomputed the exclusion from the same
offset the mask had used and so agreed with it however wrong it was.

`golden_compare` cannot stand in for this. It compares 3MF member *names* and
mesh geometry, and deliberately skips the member sha256s — the paint lives in
those bytes, so a mask that paints the wrong triangles leaves the goldens green.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
for _p in (REPO / "products" / "dog-bowl" / "generator", REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import cooper_bowl_design as design  # noqa: E402
import paint_fuzzy_skin as fuzzy  # noqa: E402
import trimesh  # noqa: E402
from ogma import bambu_project, preview as preview_lib  # noqa: E402
from styles import cooper as cooper_style  # noqa: E402

# assert_paint_ok parses these before looking at the mask; the mask is what is
# under test here, so they only have to be well-formed.
STUB_XML = "<model/>"


@pytest.fixture(scope="module")
def panel(tmp_path_factory):
    """The paw panel in print orientation, which is how the mask meets it."""
    root = tmp_path_factory.mktemp("fuzzy")
    design.configure_output(root, name="MAX", font_style="bold")
    mesh = design.build_panel(design.build_letters())
    mesh.apply_translation([0.0, 0.0, -float(mesh.bounds[0, 2])])
    return root, np.asarray(mesh.vertices), np.asarray(mesh.faces)


def test_no_paw_pad_is_painted(panel):
    root, vertices, faces = panel
    paint = fuzzy.paint_mask_for_mesh(vertices, faces, root)
    dish = fuzzy._paw_dish(vertices, faces)
    assert dish.sum() > 1000, "no paw recesses found — the filter has drifted"

    painted = paint & dish
    if painted.any():
        # The panel's top edge carries radial detail above every pad, which is
        # wall and is meant to be fuzzy. Anything painted must be up there.
        polys = design.paw_paint_silhouettes(
            z_offset=design.PANEL_BOTTOM_Z - vertices[:, 2].min(),
            rail_outer_deg=fuzzy.rail_outer_deg(root),
        )
        top_pad = max(p.bounds[3] for p in polys)
        z = vertices[faces].mean(axis=1)[painted][:, 2] + design.PANEL_BOTTOM_Z
        assert z.min() > top_pad, (
            f"{int(painted.sum())} facets on a paw flank are painted "
            f"(lowest at z={z.min():.1f}, topmost pad reaches {top_pad:.1f})"
        )


def test_no_smooth_streaks_down_the_wall(panel):
    """The wall must not carry tall smooth slivers off the pads.

    Fuzzy skin is painted per triangle, so the triangulation sets the resolution
    the mask can resolve. trimesh's cylinder does not divide the side wall up its
    height at all, and the pad boolean fans slivers off each rim: any sliver
    whose centroid landed inside a pad silhouette was left smooth over its whole
    length. 2,484 of them, up to 22.4 mm tall and 0.45 mm wide, printing as bare
    vertical streaks running down from the outermost toe of every paw. Twice
    reported off the slicer preview, and invisible to every other check here —
    the geometry is correct, only the paint is wrong.
    """
    root, vertices, faces = panel
    paint = fuzzy.paint_mask_for_mesh(vertices, faces, root)
    tri = vertices[faces]
    radius = np.hypot(tri[:, :, 0], tri[:, :, 1])
    height = tri[:, :, 2].max(axis=1) - tri[:, :, 2].min(axis=1)
    # Lying flat on the outer wall: not a pad flank, so it should be fuzzed.
    on_wall = np.abs(radius - design.WALL_OUTER_R).max(axis=1) < 0.05
    streaks = on_wall & ~paint & (height > 2.0)
    assert not streaks.any(), (
        f"{int(streaks.sum())} smooth slivers up to "
        f"{height[streaks].max():.1f} mm tall are left on the open wall"
    )


def test_pad_exclusion_tracks_the_opening_not_the_cutter(panel):
    """The silhouette must match the hole in the wall, not the whole ellipsoid.

    The cutter is centred proud of the wall, so the wall slices it off-centre and
    the opening is narrower than its semi-axes. Sizing the exclusion off the
    semi-axes made it 9% too wide before any margin, which is most of the skirt
    the streaks were carrying.
    """
    scale = design._pad_opening_scale()
    assert 0.5 < scale < 1.0, "opening cannot be wider than the cutter"
    over, depth = design.PAW_CUTTER_OVERCUT, design.PAW_RECESS_DEPTH
    assert scale == pytest.approx(
        math.sqrt(1 - (over / (depth + over)) ** 2)
    )


def test_correct_frame_is_accepted(panel):
    root, vertices, faces = panel
    paint = fuzzy.paint_mask_for_mesh(vertices, faces, root)
    fuzzy.assert_paint_ok(STUB_XML, STUB_XML, paint, vertices, faces)


def test_wrong_frame_is_rejected(panel):
    """The one-piece bug: assembly-frame offset used on a print-frame mesh."""
    root, vertices, faces = panel
    paint = fuzzy.paint_mask_for_mesh(vertices, faces, root, z_offset=0.0)
    with pytest.raises(ValueError, match="paw-dish"):
        fuzzy.assert_paint_ok(STUB_XML, STUB_XML, paint, vertices, faces)


def test_paw_wall_gets_three_loops():
    """Four loops do not fit a 3.30 mm wall; see PAW_WALL_LOOPS for the sums."""
    assert bambu_project.PAW_WALL_LOOPS == "3"
    assert bambu_project._LETTER_OVERRIDES["wall_loops"] == "4", (
        "only the paw wall is thinned; the rest of the job keeps four"
    )


# --------------------------------------------------------------------------
# What the browser preview shows.
#
# The 3D view is the picture the customer buys from, so it has to agree with the
# 3MF about which surfaces are textured. It did not: it fuzzed the whole stand
# uniformly, including the paw pads, the name plate and the seat ring the bowl
# drops into — every one of which the generator goes to some trouble to keep
# smooth, and two of which this file's other tests exist to protect.
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def assembly_panel(tmp_path_factory):
    """The paw panel in assembly coordinates, which is what the preview uses."""
    root = tmp_path_factory.mktemp("preview-fuzzy")
    design.configure_output(root, name="MAX", font_style="bold")
    return root, design.build_panel(design.build_letters())


def test_preview_mask_leaves_the_pads_and_the_letter_pockets_smooth(assembly_panel):
    root, mesh = assembly_panel
    mask_for = cooper_style.fuzzy_mask_for("assembly_paw_panel.stl", root)
    assert mask_for is not None, "the paw wall is painted, so it must have a mask"
    painted = mask_for(mesh)

    vertices, faces = np.asarray(mesh.vertices), np.asarray(mesh.faces)
    tri = vertices[faces]
    radius = np.hypot(tri[:, :, 0], tri[:, :, 1])
    area = trimesh.triangles.area(tri)

    dish = fuzzy._paw_dish(vertices, faces)
    on_pads = area[painted & dish].sum() / max(area[dish].sum(), 1e-9)
    assert on_pads < 0.05, f"{on_pads:.1%} of the paw recesses would show texture"

    # The name plate itself is textured — it is wall like any other, and left
    # smooth it was the one surface on the stand with nothing to hide behind.
    plate = radius.min(axis=1) > design.NAME_RAIL_OUTER_R - 0.5
    assert plate.any(), "no name plate found — the radius filter has drifted"
    on_plate = area[painted & plate].sum() / area[plate].sum()
    assert on_plate > 0.40, f"only {on_plate:.1%} of the name plate would show texture"

    # The pockets the letters glue into are not, and that is the half that
    # matters: fuzz in there eats the clearance the letter slides on.
    pockets = fuzzy._letter_pocket_floor(vertices, faces)
    assert pockets.sum() > 1000, "no letter pockets found — the filter has drifted"
    assert not (painted & pockets).any(), (
        f"{int((painted & pockets).sum())} letter-pocket facets would show texture"
    )


def test_the_rail_face_is_fuzzed_and_its_pockets_are_not(panel):
    """The name plate takes texture; the glyph pockets cut into it do not.

    The rail used to be excluded whole — one box covering the flat face and
    everything cut into it — because the letters seat there. Only the pockets
    need to stay smooth.
    """
    root, vertices, faces = panel
    paint = fuzzy.paint_mask_for_mesh(vertices, faces, root)
    centroids = vertices[faces].mean(axis=1)
    on_rail = fuzzy.on_name_rail_plaque(
        centroids,
        fuzzy.rail_outer_deg(root),
        z_offset=design.PANEL_BOTTOM_Z - vertices[:, 2].min(),
    )
    cut = fuzzy.letter_pocket_facets(centroids, on_rail)
    face = on_rail & ~cut
    assert cut.sum() > 1000 and face.sum() > 1000, "the rail split found nothing"
    assert not (paint & cut).any(), (
        f"{int((paint & cut).sum())} facets cut into the rail are painted"
    )
    # By area, not facet count: the boolean that cuts the pockets fans dense
    # slivers along every glyph outline, so most *facets* on the rail are edge
    # detail inside the halo while most of the *surface* is open field. Counting
    # facets reads 3-4% painted on a plate that is two-thirds textured.
    area = trimesh.triangles.area(vertices[faces])
    painted_area = area[paint & face].sum() / area[face].sum()
    assert painted_area > 0.40, (
        f"only {painted_area:.1%} of the rail face is painted — the halo has eaten it"
    )


def test_a_smooth_border_is_kept_around_every_letter(panel):
    """No fuzz within LETTER_POCKET_HALO of a pocket edge.

    The boundary between fuzzed plate and smooth pocket is the glyph outline,
    which is the one edge on the part that has to stay sharp. Fuzz reaching it
    rounds it, and 0.15 mm of rounding is more than the 0.10 mm a side the
    letter has to slide on.
    """
    root, vertices, faces = panel
    paint = fuzzy.paint_mask_for_mesh(vertices, faces, root)
    centroids = vertices[faces].mean(axis=1)
    on_rail = fuzzy.on_name_rail_plaque(
        centroids,
        fuzzy.rail_outer_deg(root),
        z_offset=design.PANEL_BOTTOM_Z - vertices[:, 2].min(),
    )
    cut = fuzzy.letter_pocket_facets(centroids, on_rail)
    face = on_rail & ~cut
    uz = fuzzy._rail_uz(centroids)
    from scipy.spatial import cKDTree

    distance, _ = cKDTree(uz[cut]).query(uz[face & paint])
    assert distance.min() >= fuzzy.LETTER_POCKET_HALO - 1e-9, (
        f"painted rail facet {distance.min():.3f} mm from a pocket edge, "
        f"inside the {fuzzy.LETTER_POCKET_HALO} mm border"
    )
    # Non-vacuous: the border has to actually be excluding something.
    assert (face & ~paint).any(), "no facet was held back — is the halo zero?"


def test_the_halo_is_at_least_one_fuzz_period():
    """A border shorter than the fuzz spacing does not put the wall back on
    nominal before the edge, which is the whole point of having one."""
    point_distance = float(
        bambu_project._PANEL_OVERRIDES["fuzzy_skin_point_distance"]
    )
    assert fuzzy.LETTER_POCKET_HALO >= point_distance


def test_preview_mask_follows_the_3mf_for_every_part(assembly_panel):
    """Each part's mask must match the fuzzy_skin the slicer is handed."""
    root, mesh = assembly_panel
    # "none", nothing painted — the rim the bowl slides into prints smooth.
    assert cooper_style.fuzzy_mask_for("assembly_top_seat_ring.stl", root) is None
    # "external" — no paint needed, the slicer fuzzes every wall of it.
    base = cooper_style.fuzzy_mask_for("cooper_base.stl", root)
    assert base is not None and base(mesh).all()
    # Not part of the stand at all.
    assert cooper_style.fuzzy_mask_for("assembly_letter_1_M.stl", root) is None


def test_bake_writes_the_mask_as_a_vertex_channel():
    """The GLB carries the mask per vertex; the viewer reads it per fragment.

    A sphere, not a cube: every vertex of a cube touches both an upper and a
    lower face, so the average lands mid-range everywhere and nothing is fully
    on or off. That is not a quirk of the test — it is exactly what happened to
    the 3,072-triangle base, and why the wall test moved into the shader.
    """
    ball = trimesh.creation.icosphere(subdivisions=3)
    upper = np.asarray(ball.triangles).mean(axis=1)[:, 2] > 0
    baked = preview_lib._bake_fuzzy_mask(ball.copy(), lambda m: upper, "test")
    level = np.asarray(baked.visual.vertex_colors)[:, 0]
    assert level.max() == 255, "a fully textured vertex must read as 1"
    assert level.min() == 0, "a fully smooth vertex must read as 0"
    # The fade is confined to the boundary, not smeared over the whole part.
    partial = ((level > 0) & (level < 255)).mean()
    assert partial < 0.25, f"{partial:.0%} of vertices are mid-fade"

    # A part with no mask bakes an explicit zero rather than leaving the
    # attribute off and relying on WebGL's default for an absent one.
    smooth = preview_lib._bake_fuzzy_mask(trimesh.creation.icosphere(), None, "test")
    assert (np.asarray(smooth.visual.vertex_colors)[:, 0] == 0).all()


def test_a_broken_mask_degrades_to_smooth_rather_than_failing():
    """A preview without texture beats no preview — but it must say so."""
    box = trimesh.creation.box()
    def explode(_mesh):
        raise RuntimeError("boom")
    baked = preview_lib._bake_fuzzy_mask(box.copy(), explode, "test")
    assert (np.asarray(baked.visual.vertex_colors)[:, 0] == 0).all()

    wrong = preview_lib._bake_fuzzy_mask(box.copy(), lambda m: np.ones(3, bool), "test")
    assert (np.asarray(wrong.visual.vertex_colors)[:, 0] == 0).all()
