# Printing and assembly

## Required parts

- One county shell
- Matching moving top
- One Outemu/Gaote Blue 3-pin MX-compatible switch
- Small amount of suitable glue for the switch flange

## Before printing a county

1. Print `counties/_fit_coupon/switch_fit_coupon.stl`.
2. Test the three square openings: 13.95, 14.10 and 14.25 mm.
3. Use the smallest opening that admits the lower switch housing without force.
4. Test the projecting MX socket on the switch stem.

The county projects currently use the tested 14.10 mm opening. Printer
calibration, material shrinkage and first-layer expansion can affect fit.

## Recommended print setup

The `.3mf` files contain two plates:

1. Fixed shell in the county's base colour
2. Moving top in the contrasting colour

Included project settings:

- Bambu Lab P2S-oriented project
- 0.16 mm layer height
- 4 wall loops
- 15% gyroid infill
- 5 top and bottom shell layers
- Supports disabled
- Fuzzy skin disabled

The moving top is intentionally printed face-down with the MX socket boss
pointing upward. Its outline therefore appears flipped on the build plate.
Turning the printed part over restores the correct assembly orientation.

## Assembly

1. Remove any brim, elephant-foot lip or loose strands from the shell pocket
   and moving-top edge.
2. Insert the switch downward through the square opening in the shell.
3. Check that the switch sits squarely on its shoulder.
4. If needed, apply a small amount of glue beneath the switch flange. Keep glue
   away from the stem and moving mechanism.
5. Turn the moving top over and press its socket onto the MX stem.
6. Click slowly several times and verify free travel.

Approximately 1.25 mm clearance per side is intentional. The irregular county
outline may wobble slightly during travel; it should not scrape or bind.

## Troubleshooting

- **Top binds:** remove edge flare/stringing; do not force it. Confirm shell and
  top came from the same generated revision.
- **Top is very loose:** confirm the MX cross is fully pressed onto the stem.
  Lateral outline clearance is not the primary stem retention.
- **Switch opening is tight:** use the fit coupon result before changing the
  generator globally.
- **Top orientation looks wrong:** it is shown face-down for printing. Flip it
  over before comparing it with the shell.
- **Switch rocks:** seat it fully and glue only beneath the flange.
