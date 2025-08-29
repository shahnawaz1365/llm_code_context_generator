#!/usr/bin/env python3
"""
pack.py — Build an LLM-ready context pack (tree + code) for any project.

Outputs:
  projects_context/<project_name>_context/
    ├─ project_context.md        # full repo tree + included file contents
    ├─ manifest.json             # metadata (num files, sizes, chunk count)
    ├─ chunks/0001.md, 0002.md…  # upload-safe UTF-8 chunks
    └─ <project_name>_context.zip# zip with everything above

Typical usage:
  python3 pack.py --root /path/to/project --force-include templates/

Notes:
  • Respects a .gptignore in the project root (fallback defaults included).
  • Only “code-ish” extensions are included by default; add folders with
    --force-include (e.g., templates/, docs/).
  • Chunking is byte-accurate and UTF-8 safe (won’t split multi-byte chars).
"""

import argparse
import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

# ---------- Defaults ----------
DEFAULT_MAX_BYTES = 9_000_000  # ~9 MB per chunk (safe for chat UIs)
DEFAULT_CODE_EXTS = {
    ".py",".ts",".tsx",".js",".jsx",".json",".yml",".yaml",".toml",".ini",
    ".md",".txt",".env.example",".env.sample",
    ".css",".scss",".html",".jinja",".j2",
    ".sql",".sh",".bash",".zsh",".ps1",".bat",
    ".go",".rs",".java",".kt",".c",".cc",".cpp",".h",".hpp",
    ".rb",".php",".swift",".dart",".lua",".r",
}

DEFAULT_IGNORE = [
    # Folders
    ".git/", ".hg/", ".svn/", ".idea/", ".vscode/",
    "__pycache__/", ".mypy_cache/", ".pytest_cache/", ".ruff_cache/",
    "node_modules/", "dist/", "build/", "out/", ".next/", ".cache/",
    ".venv/", "venv/", "static/", "media/", "storage/cache/",
    "storage/chatbots_files/", "storage/logs/", "notebooks/data/",
    # Binaries / big blobs
    "*.png","*.jpg","*.jpeg","*.gif","*.webp","*.ico","*.pdf",
    "*.mp3","*.mp4","*.wav","*.zip","*.tar","*.tar.gz","*.sqlite3",
    # Secrets
    ".env",".env.*","secrets.*","credentials.*","*service_account*.json",
    "id_rsa","id_ed25519","storage-admin.json","outbound-trunk.json",
    # Noise
    "*.lock","package-lock.json","pnpm-lock.yaml","yarn.lock",
    "*.min.js","*.min.css","*.log",
]

# ---------- Helpers ----------
def read_text_safe(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"<<UNREADABLE {p.name}: {e}>>"

def load_ignore(root: Path) -> List[str]:
    gptignore = root / ".gptignore"
    if gptignore.exists():
        lines = [ln.strip() for ln in gptignore.read_text(encoding="utf-8").splitlines()]
        return [ln for ln in lines if ln and not ln.startswith("#")]
    return DEFAULT_IGNORE

def match_ignore(rel: str, patterns: List[str]) -> bool:
    rel_unix = rel.replace("\\", "/")
    for pat in patterns:
        if pat.endswith("/"):
            if rel_unix.startswith(pat[:-1]):
                return True
        elif "*" in pat:
            rx = "^" + re.escape(pat).replace("\\*", ".*") + "$"
            if re.match(rx, rel_unix):
                return True
        else:
            if rel_unix == pat:
                return True
    return False

def iter_repo_files(root: Path, ignore: List[str]) -> Tuple[Path, str]:
    for p in root.rglob("*"):
        if p.is_dir():
            rel_dir = (str(p.relative_to(root)).replace("\\", "/") + "/")
            if match_ignore(rel_dir, ignore):
                continue
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        if match_ignore(rel, ignore):
            continue
        yield p, rel

def is_allowed_file(p: Path, include_exts: set) -> bool:
    if p.suffix in include_exts:
        return True
    if p.name.startswith(".") and p.suffix == "":  # dotfiles like ".gitignore"
        return True
    return False

def render_tree(root: Path, files_sorted: List[Tuple[Path, str]]) -> str:
    lines = ["```text", f"{root.name}/"]
    for _, rel in files_sorted:
        depth = len(Path(rel).parts) - 1
        lines.append(("  " * depth) + Path(rel).name)
    lines.append("```")
    return "\n".join(lines)

def split_by_bytes_utf8(big_text: str, max_bytes: int) -> List[bytes]:
    """Split text into byte-limited chunks without breaking UTF-8 characters."""
    data = big_text.encode("utf-8")
    chunks: List[bytes] = []
    i = 0
    while i < len(data):
        j = min(i + max_bytes, len(data))
        # back up to UTF-8 boundary if we landed in the middle of a multi-byte char
        while j > i and (data[j-1] & 0b11000000) == 0b10000000:
            j -= 1
        chunks.append(data[i:j])
        i = j
    return chunks

# ---------- Main pack ----------
def build_pack(
        root: Path,
        out_parent: Path,
        max_bytes: int,
        include_exts: set,
        force_include: List[str],
        explicit_project_name: str | None = None,
) -> int:
    """
    Build a context pack for `root` under:
      projects_context/<project_name>_context/

    Returns 0 on success, non-zero on error.
    """
    project_name = explicit_project_name or root.name
    out_dir = out_parent / f"{project_name}_context"
    chunks_dir = out_dir / "chunks"
    ignore = load_ignore(root)

    out_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir.mkdir(parents=True, exist_ok=True)

    files = []
    forced = [p.strip().replace("\\", "/").rstrip("/") + "/" for p in force_include if p.strip()]
    for p, rel in iter_repo_files(root, ignore):
        if is_allowed_file(p, include_exts) or any(rel.startswith(fi) for fi in forced):
            files.append((p, rel))
    files.sort(key=lambda x: x[1])

    # Build markdown (tree + files)
    sections: List[str] = []
    sections.append(f"# Project Context Pack\n\n- Root: `{root}`\n- Built: {datetime.utcnow().isoformat()}Z\n")
    sections.append("## Repository Tree (filtered)\n" + render_tree(root, files) + "\n")
    sections.append("## Note on Exclusions\nThis pack was generated with `.gptignore`/defaults to skip large, binary, or secret files.\n")
    sections.append("## Files\n")
    for p, rel in files:
        text = read_text_safe(p)
        if len(text) > 250_000:  # safety: prevent mega-files from blowing up the pack
            text = text[:250_000] + "\n<<TRUNCATED>>\n"
        fence_lang = p.suffix.lstrip(".")
        sections.append(f"\n### `{rel}`\n```{fence_lang}\n{text}\n```\n")

    big_text = "\n".join(sections)
    (out_dir / "project_context.md").write_text(big_text, encoding="utf-8")

    # Chunk by bytes (UTF-8 safe)
    blob_chunks = split_by_bytes_utf8(big_text, max_bytes)
    chunk_files: List[Path] = []
    for idx, blob in enumerate(blob_chunks, 1):
        cf = chunks_dir / f"{idx:04d}.md"
        cf.write_bytes(blob)
        chunk_files.append(cf)

    # Manifest
    sha = hashlib.sha256(big_text.encode("utf-8")).hexdigest()
    manifest = {
        "root": str(root),
        "built_at_utc": datetime.utcnow().isoformat() + "Z",
        "total_bytes": len(big_text.encode("utf-8")),
        "sha256": sha,
        "num_files_included": len(files),
        "num_chunks": len(chunk_files),
        "max_bytes_per_chunk": max_bytes,
        "first_chunk_path": str(chunk_files[0]) if chunk_files else None,
        "files_sample": [rel for _, rel in files[:20]],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Zip
    zip_path = out_dir / f"{project_name}_context.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(out_dir / "project_context.md", arcname="project_context.md")
        z.write(out_dir / "manifest.json", arcname="manifest.json")
        for cf in chunk_files:
            z.write(cf, arcname=f"chunks/{cf.name}")

    print(f"✅ Wrote: {out_dir/'project_context.md'}")
    print(f"✅ Chunks: {len(chunk_files)} -> {chunks_dir}")
    print(f"✅ Manifest: {out_dir/'manifest.json'}")
    print(f"✅ ZIP: {zip_path}")
    return 0

def main() -> int:
    ap = argparse.ArgumentParser(description="Create an LLM-ready context pack for your project.")
    ap.add_argument("--root", required=True, help="Project root to scan (e.g., /path/to/project)")
    ap.add_argument("--out-parent", default="projects_context", help="Parent output dir (default: projects_context)")
    ap.add_argument("--project-name", default=None, help="Override project name used for folder/zip names")
    ap.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES, help="Max bytes per chunk (default ~9MB)")
    ap.add_argument("--include-exts", default=",".join(sorted(DEFAULT_CODE_EXTS)),
                    help="Comma-separated file extensions to include")
    ap.add_argument("--force-include", default="", help="Comma-separated path prefixes to force-include (e.g., templates/,docs/)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"ERR: root {root} does not exist", file=sys.stderr)
        return 2

    out_parent = Path(args.out_parent).resolve()
    include_exts = {
        (e if e.startswith(".") else f".{e}").strip()
        for e in args.include_exts.split(",") if e.strip()
    }
    force_include = [p.strip() for p in args.force_include.split(",") if p.strip()]
    return build_pack(root, out_parent, args.max_bytes, include_exts, force_include, args.project_name)

if __name__ == "__main__":
    sys.exit(main())
