# Boundary sources and accuracy

The clicker outlines are derived from official open-government data.

## Northern Ireland

- Dataset: **OSNI Open Data – 50K Boundaries – NI Counties**
- Publisher: Ordnance Survey of Northern Ireland / Land & Property Services
- Licence: [UK Open Government Licence 3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
- Portal: https://www.opendatani.gov.uk/dataset/osni-open-data-50k-boundaries-ni-counties
- Counties: Antrim, Armagh, Derry (Londonderry in source), Down, Fermanagh and
  Tyrone

## Republic of Ireland

- Dataset: **Counties – National Statutory Boundaries – 2019**
- Publisher: Tailte Éireann
- Licence: [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/)
- Portal: https://data.gov.ie/dataset/counties-national-statutory-boundaries-2019
- Source projection: ITM (EPSG:2157), stored by this project as WGS84
  (EPSG:4326)

## Accuracy method

Each printable outline is compared with the source polygon after projection to
the common print scale. When a narrow county has been uniformly enlarged for
the MX mechanism, that scale factor is reversed before comparison.

The report records:

- **IoU (intersection over union):** percentage area agreement between source
  and printable outline. Higher is better; 100% is exact.
- **Hausdorff distance:** largest boundary deviation in millimetres at print
  scale. Lower is better.
- **Area ratio:** printable outline area divided by source area after reversing
  the mechanism-size enlargement.

Acceptance thresholds:

- IoU ≥ 99%
- Hausdorff distance ≤ 0.10 mm at print scale

Only 0.08 mm print-scale simplification is applied. The obsolete map-assembly
seam erosion was removed because these are standalone clickers.

See each county's `dimensions_and_validation.json` and the aggregate
`counties/series_fit_audit.json` for measured results.
