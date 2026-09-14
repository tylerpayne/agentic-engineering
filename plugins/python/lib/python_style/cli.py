"""Bootstrap and verification command-line interface."""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

from python_style._logging import configure_logging
from python_style._report import add
from python_style.bootstrap import bootstrap
from python_style.types import CommandOptions
from python_style.verify import verify

_LOGGER = logging.getLogger(__name__)


def main() -> int:
    """Dispatch the requested project operation.

    Returns
    -------
    int
        Zero on success, one for findings, two for invalid input.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--loglevel", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO"
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    create = subcommands.add_parser(
        "bootstrap", help="Create a Python 3.12 package without overwrites"
    )
    create.add_argument("path", type=Path)
    create.add_argument("--name", required=True)
    inspect = subcommands.add_parser(
        "verify", help="Check project configuration and Python syntax"
    )
    inspect.add_argument("path", type=Path, nargs="?", default=Path.cwd())
    inspect.add_argument(
        "--run",
        action="store_true",
        help="Also execute project-defined poe check and test tasks",
    )
    inspect.add_argument("--json", action="store_true", dest="json_output")
    for command_parser in (create, inspect):
        command_parser.add_argument(
            "--loglevel",
            choices=("DEBUG", "INFO", "WARNING", "ERROR"),
            default=argparse.SUPPRESS,
        )
    args = CommandOptions.model_validate(vars(parser.parse_args()))
    configure_logging(args.loglevel)
    _LOGGER.debug("Running %s for project %s", args.command, args.path)
    try:
        if args.command == "bootstrap":
            for path in bootstrap(args.path, args.name):
                _LOGGER.info("Created %s", path)
            _LOGGER.info(
                "Next: cd %s && uv sync && .venv/bin/python -m poethepoet check && .venv/bin/python -m poethepoet test",
                args.path,
            )
            return 0
        report = verify(args.path)
        if args.run and not report.findings:
            interpreter = (
                args.path.resolve()
                / ".venv"
                / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            )
            if not interpreter.is_file():
                raise ValueError(
                    f"Project interpreter {interpreter} is missing; run uv sync explicitly in {args.path} first."
                )
            for task in ("check", "test"):
                result = subprocess.run(
                    [str(interpreter), "-m", "poethepoet", task],
                    cwd=args.path,
                    stdout=sys.stderr,
                    check=False,
                )
                if result.returncode:
                    add(
                        report,
                        args.path,
                        "execution",
                        f"poe {task} exited with {result.returncode}",
                    )
        if args.json_output:
            # python-style: allow[print] JSON is the stdout API consumed by other processes.
            print(report.model_dump_json(indent=2))
        else:
            for finding in report.findings:
                _LOGGER.error(
                    "%s:%s: %s: %s",
                    finding.path,
                    finding.line or 0,
                    finding.rule,
                    finding.message,
                )
            if not report.findings:
                _LOGGER.info(
                    "Checked conventions passed. Review semantic record usage and module boundaries manually."
                )
        return 1 if report.findings else 0
    except (OSError, ValueError) as error:
        # python-style: allow[caught-error] Convert CLI failure into a diagnostic and exit status 2.
        _LOGGER.error("%s failed for project %s: %s", args.command, args.path, error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
