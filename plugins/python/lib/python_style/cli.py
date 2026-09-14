"""Bootstrap and verification command-line interface."""

import argparse
import subprocess
import sys
from pathlib import Path

from python_style._report import add
from python_style.bootstrap import bootstrap
from python_style.types import CommandOptions
from python_style.verify import verify


def main() -> int:
    """Dispatch the requested project operation.

    Returns
    -------
    int
        Zero on success, one for findings, two for invalid input.
    """
    parser = argparse.ArgumentParser(description=__doc__)
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
    args = CommandOptions.model_validate(vars(parser.parse_args()))
    try:
        if args.command == "bootstrap":
            for path in bootstrap(args.path, args.name):
                print(path)
            print(
                f"Next: cd {args.path} && uv sync && uv run poe check && uv run poe test"
            )
            return 0
        report = verify(args.path)
        if args.run and not report.findings:
            for task in ("check", "test"):
                result = subprocess.run(
                    ["uv", "run", "poe", task],
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
            print(report.model_dump_json(indent=2))
        else:
            for finding in report.findings:
                print(
                    f"{finding.path}:{finding.line or 0}: {finding.rule}: {finding.message}"
                )
            if not report.findings:
                print(
                    "Checked conventions passed. Review semantic record usage and module boundaries manually."
                )
        return 1 if report.findings else 0
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
