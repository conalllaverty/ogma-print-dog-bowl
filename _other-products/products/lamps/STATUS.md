# Lamps — status

<!-- Split out of the monolithic root PROJECT_STATUS.md / AGENTS.md on 2026-08-06.
     Content is verbatim: the constraint lists here were earned from physical
     prints and must not be paraphrased. -->

Two designs share this product because they share the **Bambu LED Kit 001**
hardware: `golf_tee_lamp_geometry` reuses the Boucle lamp's `build_cradle_coupon()`
and `build_baffle()`. That is a genuine shared component, not an accidental
dependency — which is why both live here rather than in separate products.

## Boucle Stack lamp

Standalone design package: `design/boucle-stack-lamp/production/` now contains
one ready-to-print eight-plate P2S project plus eight individual fallbacks:
three fuzzy Bone White shells, two smooth halo rings, a Jade White PLA Basic
diffuser, and Dark Chocolate leg-frame/cradle parts. Every plate contains one
object. Shell C is 1.2 mm for higher transmission while retaining its original
reinforced base/register interface. A→B now uses a straight continuous 22 mm
conformal bond skirt, replacing the ten scarfed tabs whose triangular shadows
were visible in the first lit assembly. Its twenty straight radial webs now
join a bed-rooted central collar without the former scalloped crown. B→C keeps
its continuous 5 mm outer band, five evenly spaced webs and 1.2 mm clearance
above Shell B's lower register.
All parts pass fit, complete-stack collision, connectivity and support-free
slice checks. The matching-band revision still requires a physical dry-fit and
bond check before replacing the previously successful rings. The production
legs embed through
the plinth wall as one watertight frame without entering the removable cradle
bore; the aligned USB path runs 20° beside the single rear leg, leaving the
two-leg front gap open. The inverted leg-frame seat/flange is 4 mm with a Ø116 outer lip and a 1.0 mm
annular locate groove that captures Shell A's Ø112 base for epoxy bonding while
keeping the cradle removable through the shell opening. A 0.6 mm radial flange
stop is followed by a 1.9 mm-high 45° bore ramp, so the Ø94 wall no longer
starts as an unsupported inward cliff and needs no breakaway puck. The removable
cradle mirrors that ramp with 0.2 mm radial clearance, leaving a 0.8 mm printable
flange lip; its key also grows outward at 45° instead of starting as a
cantilever. Plate 7 support is now explicitly off after a physical print
strung inside the supported inset: the groove and stop are short bridges, and
the support-free G-code retracts every model travel of at least 5 mm. The
diffuser uses three reduced locator pegs in
matching blind cradle sockets rather than resting loose under gravity; the
assembled clearance model has zero interference. Each halo ring carries one
outward skirt tab into a short conformal open-rim notch in its lower shell
(A or B) for hand-align before bonding, plus one hidden tapered tab into an
open-bottom notch in Shell B/C's internal register for upper-shell rotation —
without multi-pin over-constraint. The lower notches now follow each tapered
inner wall at the local rim height; the former global short-to-long cutter
caused Shell A floating-region warnings and a long channel down Shell B.
Painted shell sidewalls use the physically preferred Classic Displacement
texture at 0.30 mm thickness / 0.80 mm point distance; interiors and 4 mm
base/rim bands remain smooth.
The combined project disables infill-retraction reduction globally because
Studio ignores per-object values for that setting; the individual ring/base
fallbacks also disable it. Both final ring G-code files and all six other plates
retract every model travel of at least 5 mm. It is not wired into the
storefront.
`design/boucle-stack-lamp/fusion/` also carries a full-resolution Autodesk
Fusion mesh package: nine named watertight bodies (eight printed parts plus the
LED reference), millimetre OBJ/3MF assembly files, individual component OBJs
and a Fusion importer script. It is a 584,856-triangle mesh reference rather
than a native parametric F3D/STEP model; fuzzy skin remains slicer metadata.


## Golf Tee lamp

Standalone Golf Tee lamp work lives under `design/golf-tee-lamp/`. The revised
five-plate all-PLA P2S package uses a one-piece Ø175 Jade White translucent ball
(solid 1.6 mm shell, exact-depth relaxed dimples, 45° support-free skirt), a
Caramel Matte tee with an MH001 side-lead chase / notched reflector / 21 × 12 mm
controller passage, 3-lug bayonet with detents, and slotted spring snap. The
former Ø18 bore could not pass the supplied 19.65 × 10.65 mm controller. The
first Ø74/Ø77 snap was also physically too tight; V2 uses a Ø73.4 shaft,
Ø76.4 bead, Ø75.8 insertion throat, Ø76.8 mouth and Ø77.4 groove. The first
revised Plate 3 incorrectly narrowed to Ø74.2 before the groove and also failed
physical insertion; the corrected socket keeps Ø75.8 through that throat.
Plate 2 prints snap-foot-down with an
8 mm brim and dual 45° self-supporting cup/seat flares; this replaces the failed
seat-down orientation that put only the three protruding pins on the first
layer. The Grass Green base has a **45° inward-narrowing ballast seat** and a
matching 111.7→109.3 mm tapered cover that installs behind the felt, plus tree
supports for the pocket roof, felt recess, and fuzzy turf. See
`design/golf-tee-lamp/SPEC.md`. The first two snap sockets failed insertion;
the corrected throat remains physically unverified. The revised cable path,
bayonet,
ballast and lit-glow gates also remain open.

