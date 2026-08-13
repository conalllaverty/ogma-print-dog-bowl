"""The 3MF a customer downloads must be a valid Bambu project.

This is the closest automated proxy for the check nobody has done yet: opening
a generated file in Bambu Studio. It cannot tell you the slicer is happy — only
that the project declares the right printer, the right nozzle, PLA Matte in
every slot, plates that fit the build volume, and the colours that were asked
for. That is worth having, and it is not a substitute.

`audit_3mf.py` remains runnable as a script against any file:

    python tests/audit_3mf.py path/to/Some_P2S.3mf --stand '#AE835B'
    python tests/audit_3mf.py --generate

Reading its table is how you see *what* a failing check measured. These wrap it
so a break fails CI rather than waiting for someone to remember.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
for _p in (REPO / "tests", REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import audit_3mf  # noqa: E402


@pytest.fixture(scope="module")
def audited():
    """Build one 3MF and audit it once — the build is several seconds."""
    path, stand, letters = audit_3mf.generate_one()
    result = audit_3mf.run_audit(path, stand, letters)
    assert result.checks, "the audit ran no checks at all"
    return result


def test_every_check_passes(audited):
    failures = [
        f"{label}: {detail}" for ok, label, detail in audited.checks if not ok
    ]
    assert not failures, "3MF audit failures:\n  " + "\n  ".join(failures)


def test_the_expected_number_of_checks_ran(audited):
    """A check that silently stops running is a check that always passes.

    The count is asserted loosely — adding checks is good and should not fail
    the suite — but it cannot quietly collapse to a handful.
    """
    assert len(audited.checks) >= 14, (
        f"only {len(audited.checks)} checks ran; the audit covered 14"
    )


def test_the_generated_project_is_a_readable_archive(audited):
    labels = [label for _ok, label, _d in audited.checks]
    assert "archive integrity" in labels
