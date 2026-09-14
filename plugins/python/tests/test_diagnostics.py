"""Exercise rationale checking, logging, and safe diagnostics."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest
from python_style._smells import check_smells
from python_style.bootstrap import bootstrap
from python_style.types import Report
from python_style.verify import verify


@pytest.mark.parametrize(
    ("source", "rule"),
    [
        ('getattr(external, "name", None)', "dynamic-attrs"),
        ('setattr(external, "name", "value")', "dynamic-attrs"),
        ('print("progress")', "print"),
        ('values.get("missing", None)', "forgiving-get"),
        ('values.setdefault("missing", 0)', "forgiving-get"),
        ("try:\n    fail()\nexcept ValueError:\n    pass", "caught-error"),
    ],
)
def test_smells_require_rationale(source: str, rule: str) -> None:
    """Comments justify review exceptions while bare smells are reported.

    Parameters
    ----------
    source : str
        Source containing a smell.
    rule : str
        Expected review rule.
    """
    report = Report(project="sample")
    check_smells(ast.parse(source), source, Path("sample.py"), report)
    assert any(finding.rule == rule for finding in report.findings)
    if rule == "caught-error":
        explained = source.replace(
            "    pass",
            "    # python-style: allow[caught-error] Expected absence is handled by the caller.\n    pass",
        )
    else:
        explained = f"# python-style: allow[{rule}] Required external protocol behavior.\n{source}"
    report = Report(project="sample")
    check_smells(ast.parse(explained), explained, Path("sample.py"), report)
    assert not report.findings


def test_string_is_not_rationale() -> None:
    """A string literal cannot suppress a review finding."""
    source = '"# python-style: allow[print] pretend explanation"\nprint("status")'
    report = Report(project="sample")
    check_smells(ast.parse(source), source, Path("sample.py"), report)
    assert any(finding.rule == "print" for finding in report.findings)


def test_reraise_is_not_swallowed() -> None:
    """A direct re-raise requires no consumed-error rationale."""
    source = "try:\n    fail()\nexcept ValueError:\n    raise"
    report = Report(project="sample")
    check_smells(ast.parse(source), source, Path("sample.py"), report)
    assert not report.findings


def test_configuration_does_not_leak_input(tmp_path: Path) -> None:
    """Invalid wire values must not be reproduced in error reports.

    Parameters
    ----------
    tmp_path : Path
        Temporary project directory.
    """
    bootstrap(tmp_path, "sample")
    path = tmp_path / "pyproject.toml"
    path.write_text(
        path.read_text().replace(
            'check = ["check:lint", "check:format", "check:types"]',
            'check = {password = "secret-canary"}',
        )
    )
    report = verify(tmp_path)
    assert report.findings
    assert "secret-canary" not in report.model_dump_json()
    assert "tool.poe.tasks.check" in report.model_dump_json()


@pytest.mark.parametrize("verbosity", ["--verbose", "--quiet"])
def test_json_stdout_and_verbosity(tmp_path: Path, verbosity: str) -> None:
    """Machine output remains valid JSON at different logging levels.

    Parameters
    ----------
    tmp_path : Path
        Temporary project directory.
    verbosity : str
        Logging flag.
    """
    bootstrap(tmp_path, "sample")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from python_style.cli import main; raise SystemExit(main())",
            "verify",
            str(tmp_path),
            "--json",
            verbosity,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert not Report.model_validate_json(result.stdout).findings
    assert ("DEBUG" in result.stderr) == (verbosity == "--verbose")


def test_cli_failure_is_loud_and_has_context(tmp_path: Path) -> None:
    """Even quiet mode retains the invalid value and a failing exit code.

    Parameters
    ----------
    tmp_path : Path
        Temporary project directory.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from python_style.cli import main; raise SystemExit(main())",
            "--quiet",
            "bootstrap",
            str(tmp_path),
            "--name",
            "bad-name!",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert not result.stdout
    assert "bad-name!" in result.stderr
    assert "ERROR" in result.stderr
