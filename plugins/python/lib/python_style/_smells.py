"""Flag deliberate-exception conventions for human review."""

import ast
import io
import tokenize
from pathlib import Path

from python_style._report import add
from python_style.types import Report


def check_smells(tree: ast.Module, source: str, path: Path, report: Report) -> None:
    """Report smells lacking a nearby explicit rationale comment.

    Parameters
    ----------
    tree : ast.Module
        Parsed source.
    source : str
        Source text, used to locate real comments.
    path : Path
        Source file.
    report : Report
        Destination for findings.
    """
    comments = {
        token.start[0]: token.string
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.COMMENT
    }
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Call, ast.ExceptHandler)):
            continue
        rule = ""
        if isinstance(node, ast.Call):
            name = ast.unparse(node.func)
            if name in {"getattr", "setattr", "builtins.getattr", "builtins.setattr"}:
                rule = "dynamic-attrs"
            elif name in {"print", "builtins.print"}:
                rule = "print"
            elif isinstance(node.func, ast.Attribute) and node.func.attr in {
                "get",
                "setdefault",
            }:
                rule = "forgiving-get"
        elif isinstance(node, ast.ExceptHandler):
            # Nested raises do not prove every path reraises; human review remains necessary.
            if not any(
                isinstance(child, ast.Raise)
                for statement in node.body
                for child in ast.walk(statement)
            ):
                rule = "caught-error"
        if not rule:
            continue
        marker = f"# python-style: allow[{rule}] "
        lines = (node.lineno - 1, node.lineno)
        if isinstance(node, ast.ExceptHandler):
            lines += (node.lineno + 1,)
        if any(
            line in comments
            and comments[line].startswith(marker)
            and comments[line][len(marker) :].strip()
            for line in lines
        ):
            continue
        add(
            report,
            path,
            rule,
            f"Review {rule}; use a nearby '{marker}<reason>' comment for a justified exception.",
            node.lineno,
        )
