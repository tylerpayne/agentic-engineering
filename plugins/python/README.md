# python

Python conventions as a skill, with a `python-style` bootstrap and verification
CLI. Prepare its Python 3.12 environment explicitly with uv and the included lockfile.

```sh
claude plugin install python@tylerpayne
```

Other agents can download the bundle from the site and read
`skills/python/SKILL.md`. Keep the bundle intact. `bin/python-style` invokes the
packaged CLI from its own .venv without requiring Claude Code, changing the
calling directory, or syncing dependencies. First run
`uv sync --locked --project /path/to/python` to prepare that environment.

```sh
/path/to/python/bin/python-style bootstrap ./example --name example
cd example
uv sync
.venv/bin/python -m poethepoet check
.venv/bin/python -m poethepoet test
.venv/bin/python -m pre_commit install
/path/to/python/bin/python-style verify . --json
/path/to/python/bin/python-style verify . --run
/path/to/python/bin/python-style verify . --loglevel DEBUG
```

Bootstrap creates a src-layout package, Hatchling build configuration, uv Python
pin, Poe tasks, Ruff and NumPy docstring settings, ty, pytest, Pydantic v2,
and a local pre-commit hook. It never overwrites existing scaffold files.
Run `uv sync` to create the project lockfile and environment, and commit uv.lock.
For workspaces, add packages to the root uv workspace and sync from there.

Verification checks configuration, task wiring, annotations, fixed-key dict
literals, record-module placement, file size, and implementations in __init__.py.
It checks this scaffold's string and sequence Poe task profile; other valid Poe
forms are reported as unsupported configuration. It checks a package at a time,
not inherited workspace settings. Python 3.12 is the preferred verification
profile; a project deliberately requiring a newer interpreter needs review.

Static verification is read-only and exits 1 for findings, 2 for invalid CLI
input or bootstrap failures. `--run` runs the target's check and test tasks only
when static checks pass. It executes project code using the target’s existing .venv; it never creates or
syncs environments. Prepare the target with an explicit uv sync first.
JSON reports are Pydantic wire models; diagnostics from task subprocesses go to
stderr. AST checks are heuristics, not proof: review record semantics, private
names, serialization boundaries, docstrings, and module responsibilities too.

The CLI configures standard-library logging to stderr. Use `--loglevel DEBUG|INFO|WARNING|ERROR`
before or after the subcommand; the default is INFO. DEBUG includes diagnostic
detail, WARNING suppresses informational messages, and ERROR emits errors only. `--json` is the stdout interface for other processes;
normal progress and findings use logging. Scaffolds include `_logging.py` with
`configure_logging`; call it from your application entry point and expose
`--loglevel` in any CLI you add. Do not configure root logging on library
import.

The skill also covers dynamic attribute access, intentionally consumed
exceptions, forgiving dict lookups, stdout contracts, and informative failures
without leaking secrets. Static review findings use the rules `dynamic-attrs`,
`caught-error`, `forgiving-get`, and `print`. Document a justified exception with
`# python-style: allow[rule] explanation` next to the statement. These are review
conventions, not blanket bans; the checker cannot establish ownership or intent.

Develop this plugin from this directory:

```sh
uv sync --locked
.venv/bin/python -m poethepoet format
.venv/bin/python -m poethepoet check
.venv/bin/python -m poethepoet fix
.venv/bin/python -m poethepoet test
uv build
```

Pre-commit intentionally uses `uv run --locked poe check` to reject a stale
lockfile. This exception may sync the environment; regular CLI and task
execution still uses the prepared virtualenv directly.
