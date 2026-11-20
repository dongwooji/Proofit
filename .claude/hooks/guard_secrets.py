"""PreToolUse hook (Bash | PowerShell).

Blocks git commands that would commit secrets or personal data:
  - `git add -f/--force` on a protected path
  - `git commit` while a protected path is staged

Protected: .env* (except .env.example), *.db / *.sqlite*, data/, backups/,
exports/, uploads/, secrets/, *.pem, *.key, credentials*.json, token*.json
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import PurePosixPath

PROTECTED_DIRS = ("data", "backups", "exports", "uploads", "secrets")
PROTECTED_NAMES = (
    ".env",
    ".env.*",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "*.pem",
    "*.key",
    "credentials*.json",
    "token*.json",
)
ALLOWED_NAMES = (".env.example",)


def is_protected(path: str) -> bool:
    p = PurePosixPath(path.replace("\\", "/").strip().strip("\"'"))
    if p.name in ALLOWED_NAMES:
        return False
    if any(part in PROTECTED_DIRS for part in p.parts[:-1]) or p.name in PROTECTED_DIRS:
        return True
    return any(fnmatch(p.name, pattern) for pattern in PROTECTED_NAMES)


def staged_files(cwd: str | None) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [line for line in out.stdout.splitlines() if line.strip()]


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def main() -> None:
    payload = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    command: str = (payload.get("tool_input") or {}).get("command") or ""
    cwd = payload.get("cwd")

    if not re.search(r"\bgit\b", command):
        return

    # 1) Forced add of a protected path (bypasses .gitignore)
    for segment in re.split(r"&&|\|\||;|\|", command):
        tokens = segment.split()
        if "git" not in tokens:
            continue
        rest = tokens[tokens.index("git") + 1 :]
        if rest[:1] == ["add"] and any(t in ("-f", "--force") for t in rest):
            hits = [t for t in rest[1:] if not t.startswith("-") and is_protected(t)]
            if hits:
                deny(f"Proofit guard: refusing forced add of protected path(s): {', '.join(hits)}")

    # 2) Commit while protected files are staged
    if re.search(r"\bgit\b[^;&|]*\bcommit\b", command):
        hits = [f for f in staged_files(cwd) if is_protected(f)]
        if hits:
            deny(
                "Proofit guard: protected file(s) are staged and must not be committed: "
                + ", ".join(hits)
                + ". Unstage them with `git rm --cached <file>` (the file itself is kept)."
            )


if __name__ == "__main__":
    main()
