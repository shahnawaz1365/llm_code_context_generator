#!/usr/bin/env python3
"""
redact_secrets.py — Redact secrets (API keys, tokens, passwords) from a project.

Two modes:
  1) In-place (default): modifies matching files directly.
  2) Mirror mode: write a redacted COPY to another directory (originals untouched).

Examples:
  # In-place redact a project
  python3 redact_secrets.py /path/to/project

  # Create a safe copy at /tmp/project_sanitized
  python3 redact_secrets.py /path/to/project --mirror-out /tmp/project_sanitized
"""

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Iterable

TEXT_EXTS = {
    ".py",".json",".yml",".yaml",".toml",".ini",".env",".html",".htm",
    ".md",".txt",".js",".ts",".css",".scss",".tsx",".jsx",
}

# Patterns to redact (simple but effective)
REPLACERS: list[tuple[re.Pattern, str]] = [
    # KEY= "value" / KEY='value'
    (re.compile(r'(?i)\b(api[-_ ]?key|secret|token|password)\s*=\s*([\'"])[^\'"\n]+([\'"])'), r'\1=\2<REDACTED>\3'),
    # KEY: value   (YAML / JSON-ish / env)
    (re.compile(r'(?i)\b(api[-_ ]?key|secret|token|password)\s*[:]\s*[\'"]?[^\'"\n]+'), r'\1: <REDACTED>'),
]

def is_text_file(p: Path) -> bool:
    if p.suffix.lower() in TEXT_EXTS:
        return True
    # Allow dotfiles like ".env", ".gptignore" (no suffix)
    if p.name.startswith(".") and p.suffix == "":
        return True
    return False

def iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_file():
            yield p

def redact_string(s: str) -> str:
    out = s
    for rx, repl in REPLACERS:
        out = rx.sub(repl, out)
    return out

def redact_file_inplace(p: Path) -> bool:
    try:
        src = p.read_text(encoding="utf-8")
    except Exception:
        return False
    red = redact_string(src)
    if red != src:
        p.write_text(red, encoding="utf-8")
        print(f"Redacted: {p}")
        return True
    return False

def redact_to_mirror(src_root: Path, dst_root: Path, p: Path) -> None:
    rel = p.relative_to(src_root)
    dst_path = dst_root / rel
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    if is_text_file(p):
        try:
            s = p.read_text(encoding="utf-8")
        except Exception:
            # fall back to raw copy if unreadable text
            shutil.copy2(p, dst_path)
            return
        red = redact_string(s)
        dst_path.write_text(red, encoding="utf-8")
    else:
        # binary or unknown: copy as-is
        shutil.copy2(p, dst_path)

def main() -> int:
    ap = argparse.ArgumentParser(description="Redact secrets from a project (in-place or to a mirror directory).")
    ap.add_argument("root", help="Path to the project root")
    ap.add_argument("--mirror-out", default=None, help="If set, write a redacted COPY to this directory (originals untouched)")
    args = ap.parse_args()

    src_root = Path(args.root).resolve()
    if not src_root.exists():
        print(f"ERR: root {src_root} does not exist", file=sys.stderr)
        return 2

    if args.mirror_out:
        dst_root = Path(args.mirror_out).resolve()
        if dst_root.exists() and any(dst_root.iterdir()):
            print(f"ERR: mirror-out {dst_root} already exists and is not empty", file=sys.stderr)
            return 3
        print(f"🔐 Creating redacted mirror at: {dst_root}")
        for p in iter_files(src_root):
            redact_to_mirror(src_root, dst_root, p)
        print("✅ Mirror redaction complete.")
        return 0

    # In-place mode
    print(f"🔐 Redacting in place under: {src_root}")
    changed = 0
    for p in iter_files(src_root):
        if is_text_file(p):
            changed += 1 if redact_file_inplace(p) else 0
    print(f"✅ In-place redaction complete. Files changed: {changed}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
