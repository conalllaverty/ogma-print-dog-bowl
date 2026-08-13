# County boundary sources

Boundaries in this folder are rebuilt from official open government data:

## Northern Ireland (6 counties)

- **Dataset:** OSNI Open Data – 50K Boundaries – NI Counties
- **Publisher:** Ordnance Survey of Northern Ireland / Land & Property Services
- **Licence:** [UK Open Government Licence (OGL)](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
- **Portal:** https://www.opendatani.gov.uk/dataset/osni-open-data-50k-boundaries-ni-counties
- **Counties:** Antrim, Armagh, Derry (source name Londonderry), Down, Fermanagh, Tyrone

## Republic of Ireland (26 counties)

- **Dataset:** Counties – National Statutory Boundaries – 2019
- **Publisher:** Tailte Éireann
- **Licence:** [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/)
- **Portal:** https://data.gov.ie/dataset/counties-national-statutory-boundaries-2019
- **Projection in source:** ITM (EPSG:2157), stored here as WGS84 (EPSG:4326)

## Notes

- These are traditional / statutory county outlines for the 32 counties of Ireland.
- Water bodies such as Lough Neagh remain as gaps between counties.
- Printable clickers apply light 0.08 mm simplification at print scale; they
  are not cadastral-grade. No map-assembly seam inset is applied.
- Each generated report records polygon IoU and Hausdorff boundary deviation
  against these source polygons. Intentional uniform enlargement for the MX
  mechanism is reversed before comparison.
