"""PostToolUse hook (Edit | Write).

When a .py file is edited, runs `ruff check --fix` and `ruff format` on it.
Remaining lint errors are reported back to Claude as additional context.
Silently does nothing if ruff is not installed.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path


def find_ruff(project_dir: Path) -> list[str] | None:
    for candidate in (
        project_dir / ".venv" / "Scripts" / "ruff.exe",
        project_dir / ".venv" / "bin" / "ruff",
    ):
        if candidate.exists():
            return [str(candidate)]
    on_path = shutil.which("ruff")
    if on_path:
        return [on_path]
    if importlib.util.find_spec("ruff") is not None:
        return [sys.executable, "-m", "ruff"]
    return None


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
    )


def main() -> None:
    payload = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    tool_input = payload.get("tool_input") or {}
    tool_response = payload.get("tool_response") or {}
    file_path = tool_input.get("file_path") or tool_response.get("filePath")
    if not file_path or not file_path.endswith(".py"):
        return

    path = Path(file_path)
    if not path.exists():
        return

    project_dir = Path(payload.get("cwd") or path.parent)
    ruff = find_ruff(project_dir)
    if ruff is None:
        return

    run([*ruff, "check", "--fix", "--quiet", str(path)])
    run([*ruff, "format", "--quiet", str(path)])
    remaining = run([*ruff, "check", "--output-format", "concise", str(path)])

    if remaining.returncode != 0 and remaining.stdout.strip():
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": "ruff found issues it could not auto-fix:\n"
                        + remaining.stdout.strip(),
                    }
                }
            )
        )


if __name__ == "__main__":
    main()
