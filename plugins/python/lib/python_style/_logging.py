"""Application logging setup; libraries should only obtain named loggers."""

import logging


def configure_logging(verbose: int = 0, quiet: bool = False) -> None:
    """Configure stderr diagnostics at the application's entry point.

    Parameters
    ----------
    verbose : int
        Verbosity count; one or more enables debug logging.
    quiet : bool
        Suppress informational messages while preserving errors and warnings.
    """
    level = logging.WARNING if quiet else logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s", force=True)
