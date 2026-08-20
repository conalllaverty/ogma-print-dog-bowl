"""The generator must build without a GL stack.

pyrender is installed separately with `--no-deps` (requirements-render.txt), so
it is absent anywhere that installs only requirements.txt — CI included. That was
fine by design: `renders.build()` is documented as non-fatal because "the 3MF is
the deliverable". The import disagreed with the design, and because
`ogma.render` imported pyrender at module scope the absence propagated up
through `renders.py` to `pipeline.py` and took every golden case with it.

CI had been red on every commit for the whole of its run history, including
documentation-only ones, reporting `FAILED TO BUILD — No module named
'pyrender'` for all six cases. The cost was not the red tick: it was that the
geometry safety net had not run in CI at all, while passing locally on the one
machine that happened to have pyrender installed.

So this is the test that would have caught it, and it deliberately does not
depend on whether the machine running it has pyrender. It hides the module and
checks the thing CI actually does.

Run:  .venv/bin/python -m pytest tests/test_render_optional.py -q
"""

from __future__ import annotations

import importlib
import importlib.abc
import subprocess
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GENERATOR = REPO / "products" / "dog-bowl" / "generator"
SHARED = REPO / "shared"


def _run_without_pyrender(body: str) -> subprocess.CompletedProcess:
    """Run `body` in a fresh interpreter where importing pyrender fails.

    A subprocess rather than a meta-path hook in-process: the modules under test
    are almost certainly imported already by the rest of the suite, and a hook
    cannot un-import them. A clean interpreter is the only honest way to test an
    import.
    """
    script = textwrap.dedent(
        f"""
        import sys, importlib.abc

        class Block(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path=None, target=None):
                if name == "pyrender" or name.startswith("pyrender."):
                    raise ImportError("pyrender is not installed")
                return None

        sys.meta_path.insert(0, Block())
        sys.path.insert(0, {str(GENERATOR)!r})
        sys.path.insert(0, {str(SHARED)!r})
        {body}
        """
    )
    return subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=300
    )


def test_the_pipeline_imports_without_pyrender():
    """The one that was broken. `import pipeline` reaches ogma.render."""
    result = _run_without_pyrender("import pipeline; print('ok')")
    assert result.returncode == 0, result.stderr[-2000:]
    assert "ok" in result.stdout


def test_every_style_module_imports_without_pyrender():
    """Each style pulls in the generator; none may need a GL stack to load."""
    result = _run_without_pyrender(
        "import styles\n"
        "        for s in styles.all_styles():\n"
        "            assert s.id\n"
        "        print('ok')"
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert "ok" in result.stdout


def test_render_reports_itself_unavailable_and_returns_nothing():
    """`render()` promises never to raise for rendering reasons. Including this one."""
    result = _run_without_pyrender(
        "from ogma import render\n"
        "        assert render.AVAILABLE is False\n"
        "        assert render.render([], '/tmp/ogma-render-test') == []\n"
        "        print('ok')"
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert "ok" in result.stdout


def test_render_is_available_when_pyrender_is_installed():
    """The other direction, so this file cannot pass by breaking rendering."""
    pyrender = importlib.util.find_spec("pyrender")
    if pyrender is None:
        import pytest

        pytest.skip("pyrender not installed in this environment")

    sys.path.insert(0, str(SHARED))
    from ogma import render

    assert render.AVAILABLE is True
