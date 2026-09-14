"""Application logging setup; libraries should only obtain named loggers."""

import logging


def configure_logging(loglevel: str = "INFO") -> None:
    """Configure stderr diagnostics at the application's entry point.

    Parameters
    ----------
    loglevel : str
        Minimum severity: DEBUG, INFO, WARNING, or ERROR.

    Raises
    ------
    ValueError
        If the supplied severity is unsupported.
    """
    if loglevel not in ("DEBUG", "INFO", "WARNING", "ERROR"):
        raise ValueError(
            f"Unsupported loglevel {loglevel!r}; expected DEBUG, INFO, WARNING, or ERROR"
        )
    logging.basicConfig(level=loglevel, format="%(levelname)s: %(message)s", force=True)
