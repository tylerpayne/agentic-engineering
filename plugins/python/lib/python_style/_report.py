"""Append structured verification findings."""

from pathlib import Path

from pydantic import ValidationError

from python_style.types import Finding, Report, TaskReferenceError, ValidationDetail


def configuration_error(error: Exception) -> str:
    """Describe a configuration failure without echoing untrusted values.

    Parameters
    ----------
    error : Exception
        Parser or validation failure, potentially containing secrets.

    Returns
    -------
    str
        Safe locations and error categories without raw input or context.
    """
    if isinstance(error, TaskReferenceError):
        return f"Missing or cyclic task: {error.task!r}"
    if isinstance(error, ValidationError):
        details = [
            ValidationDetail.model_validate(item)
            for item in error.errors(
                include_input=False, include_context=False, include_url=False
            )
        ]
        return "; ".join(
            f"{'.'.join(str(part) for part in detail.loc)}: {detail.type}"
            for detail in details
        )
    return f"Invalid configuration ({type(error).__name__}); inspect the named file. Raw parser input omitted."


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
