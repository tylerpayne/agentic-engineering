"""Run static project convention checks."""

from pathlib import Path

from python_style._config import check_config
from python_style._source import check_source
from python_style.types import Report


def verify(root: Path) -> Report:
    """Inspect a package without executing its code.

    Parameters
    ----------
    root : Path
        Package root containing pyproject.toml.

    Returns
    -------
    Report
        Static findings; an empty list means checked conventions passed.
    """
    root = root.resolve()
    report = Report(project=str(root))
    check_config(root, report)
    check_source(root, report)
    return report
