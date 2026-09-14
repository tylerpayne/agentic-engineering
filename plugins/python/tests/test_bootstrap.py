"""Test scaffolding and verification behavior."""

from pathlib import Path

import pytest
from python_style.bootstrap import bootstrap
from python_style.verify import verify


def test_scaffold_passes(tmp_path: Path) -> None:
    """Generated projects satisfy the static profile.

    Parameters
    ----------
    tmp_path : Path
        Temporary project directory.
    """
    bootstrap(tmp_path, "sample-project")
    assert not verify(tmp_path).findings


def test_collision_preserves_files(tmp_path: Path) -> None:
    """A collision prevents every scaffold write.

    Parameters
    ----------
    tmp_path : Path
        Temporary project directory.
    """
    existing = tmp_path / ".python-version"
    existing.write_text("keep me")
    with pytest.raises(ValueError, match="overwrite"):
        bootstrap(tmp_path, "sample")
    assert existing.read_text() == "keep me"
    assert not (tmp_path / "pyproject.toml").exists()


@pytest.mark.parametrize("name", ["../escape", "class", "with spaces", "Foo", "2bad"])
def test_invalid_names(tmp_path: Path, name: str) -> None:
    """Invalid package names cannot escape the destination.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory.
    name : str
        Invalid package name.
    """
    with pytest.raises(ValueError):
        bootstrap(tmp_path, name)
    assert not list(tmp_path.iterdir())


def test_source_findings(tmp_path: Path) -> None:
    """Report implementations in init and missing type annotations.

    Parameters
    ----------
    tmp_path : Path
        Temporary project directory.
    """
    bootstrap(tmp_path, "sample")
    (tmp_path / "src/sample/__init__.py").write_text(
        "def broken(value):\n    return value\n"
    )
    rules = {finding.rule for finding in verify(tmp_path).findings}
    assert {"init", "annotations"}.issubset(rules)


def test_wrong_tasks_and_hook(tmp_path: Path) -> None:
    """Detect missing type checks and an ineffective hook.

    Parameters
    ----------
    tmp_path : Path
        Temporary project directory.
    """
    bootstrap(tmp_path, "sample")
    config = tmp_path / "pyproject.toml"
    config.write_text(config.read_text().replace('"ty check"', '"echo skipped"'))
    hook = tmp_path / ".pre-commit-config.yaml"
    hook.write_text(
        hook.read_text().replace("pass_filenames: false", "pass_filenames: true")
    )
    rules = {finding.rule for finding in verify(tmp_path).findings}
    assert {"tasks", "pre-commit"}.issubset(rules)


def test_record_and_size_findings(tmp_path: Path) -> None:
    """Detect literal records, misplaced dataclasses, and large files.

    Parameters
    ----------
    tmp_path : Path
        Temporary project directory.
    """
    bootstrap(tmp_path, "sample")
    (tmp_path / "src/sample/work.py").write_text(
        "from dataclasses import dataclass\n@dataclass\nclass Record:\n"
        "    value: str\nrecord = {'value': 'example'}\n" + "# filler\n" * 301
    )
    rules = {finding.rule for finding in verify(tmp_path).findings}
    assert {"records", "types", "size"}.issubset(rules)


def test_cycle_is_reported(tmp_path: Path) -> None:
    """Task cycles are findings rather than recursion crashes.

    Parameters
    ----------
    tmp_path : Path
        Temporary project directory.
    """
    bootstrap(tmp_path, "sample")
    config = tmp_path / "pyproject.toml"
    config.write_text(
        config.read_text().replace(
            '"check:lint", "check:format", "check:types"', '"check"'
        )
    )
    assert any("cyclic" in finding.message for finding in verify(tmp_path).findings)
