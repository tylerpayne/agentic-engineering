"""Append structured verification findings."""

from pathlib import Path

from python_style.types import Finding, Report


def add(
    report: Report, path: Path, rule: str, message: str, line: int | None = None
) -> None:
    """Append one finding.

    Parameters
    ----------
    report : Report
        Destination report.
    path : Path
        Relevant file.
    rule : str
        Convention identifier.
    message : str
        Explanation.
    line : int | None
        Optional source line.
    """
    report.findings.append(
        Finding(path=str(path), rule=rule, message=message, line=line)
    )
