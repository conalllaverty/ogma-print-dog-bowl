#!/usr/bin/env python3
"""GAA county colours for the Ireland county-clicker series.

Shell / top assignment follows the Tyrone prototype: the jersey's lighter or
primary field colour is the fixed shell, and the contrasting colour is the
moving top. Offaly drops the middle white so the top remains readable.
Kildare is all-white in kit form, so the top uses gold for contrast.
"""

from __future__ import annotations

# (shell_name, shell_hex, top_name, top_hex)
COUNTY_COLOURS: dict[str, tuple[str, str, str, str]] = {
    "Antrim": ("Antrim Saffron", "#F0C400", "Antrim White", "#FFFFFF"),
    "Armagh": ("Armagh Orange", "#E87722", "Armagh White", "#FFFFFF"),
    "Carlow": ("Carlow Red", "#C8102E", "Carlow Yellow", "#F7D117"),
    "Cavan": ("Cavan Blue", "#0033A0", "Cavan White", "#FFFFFF"),
    "Clare": ("Clare Saffron", "#F0C400", "Clare Blue", "#0033A0"),
    "Cork": ("Cork Red", "#C8102E", "Cork White", "#FFFFFF"),
    "Derry": ("Derry White", "#FFFFFF", "Derry Red", "#C8102E"),
    "Donegal": ("Donegal Gold", "#F0C400", "Donegal Green", "#009A44"),
    "Down": ("Down Red", "#C8102E", "Down Black", "#1A1A1A"),
    "Dublin": ("Dublin Sky Blue", "#6EC1E4", "Dublin Navy", "#0C2340"),
    "Fermanagh": ("Fermanagh Green", "#009A44", "Fermanagh White", "#FFFFFF"),
    "Galway": ("Galway Maroon", "#800000", "Galway White", "#FFFFFF"),
    "Kerry": ("Kerry Green", "#009A44", "Kerry Gold", "#F0C400"),
    "Kildare": ("Kildare White", "#FFFFFF", "Kildare Gold", "#F0C400"),
    "Kilkenny": ("Kilkenny Black", "#1A1A1A", "Kilkenny Amber", "#F0A000"),
    "Laois": ("Laois Blue", "#0033A0", "Laois White", "#FFFFFF"),
    "Leitrim": ("Leitrim Green", "#009A44", "Leitrim Gold", "#F0C400"),
    "Limerick": ("Limerick Green", "#009A44", "Limerick White", "#FFFFFF"),
    "Longford": ("Longford Blue", "#0033A0", "Longford Gold", "#F0C400"),
    "Louth": ("Louth Red", "#C8102E", "Louth White", "#FFFFFF"),
    "Mayo": ("Mayo Green", "#009A44", "Mayo Red", "#C8102E"),
    "Meath": ("Meath Green", "#009A44", "Meath Gold", "#F0C400"),
    "Monaghan": ("Monaghan White", "#FFFFFF", "Monaghan Blue", "#0033A0"),
    "Offaly": ("Offaly Green", "#009A44", "Offaly Gold", "#F0C400"),
    "Roscommon": ("Roscommon Primrose", "#F5E153", "Roscommon Blue", "#0033A0"),
    "Sligo": ("Sligo Black", "#1A1A1A", "Sligo White", "#FFFFFF"),
    "Tipperary": ("Tipperary Blue", "#0033A0", "Tipperary Gold", "#F0C400"),
    "Tyrone": ("Tyrone White", "#FFFFFF", "Tyrone Red", "#D71920"),
    "Waterford": ("Waterford White", "#FFFFFF", "Waterford Blue", "#0033A0"),
    "Westmeath": ("Westmeath Maroon", "#800000", "Westmeath White", "#FFFFFF"),
    "Wexford": ("Wexford Purple", "#5C2D91", "Wexford Gold", "#F0C400"),
    "Wicklow": ("Wicklow Blue", "#0033A0", "Wicklow Gold", "#F0C400"),
}

COUNTIES = tuple(sorted(COUNTY_COLOURS))
