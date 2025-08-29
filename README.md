# LLM Code Context Generator

Create an **LLM-ready project context** (repo tree + source code) from any project and auto-split it into upload-safe Markdown chunks. Ideal for starting a **new ChatGPT chat** with your entire codebase available.

- Pure Python (no 3rd-party deps)
- Respects project-level **`.gptignore`** (like `.gitignore` but for LLMs)
- Optional **secret redaction** (in-place or into a mirrored “safe copy”)
- Output organized under a single folder: `projects_context/<project>_context/` and `<project>_context.zip`

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![OpenAI](https://img.shields.io/badge/OpenAI-Whisper%20&%20GPT-black?logo=openai)
![Status](https://img.shields.io/badge/Status-MVP%20Complete-brightgreen)
---

## What it produces

For a project at `/path/to/my_project`:

```
projects_context/
└── my_project_context/
    ├── project_context.md       # Repo tree + included file contents
    ├── manifest.json            # Metadata (num files, sizes, chunks)
    ├── chunks/
    │   ├── 0001.md
    │   └── 0002.md  (only if needed)
    └── my_project_context.zip   # Everything zipped for single-file upload
```

If your project is small, you’ll likely get just `chunks/0001.md`.

---

## Quickstart

1) **Clone** this repo and enter it:
```bash
git clone https://github.com/yourname/llm-code-context-generator.git
cd llm-code-context-generator
```

2) (Optional) add a `.gptignore` to your target project (template under `examples/.gptignore`).

3) **Redact secrets** (optional):
```bash
# In-place (modifies files that match the patterns)
python3 src/redact_secrets.py /path/to/your/project

# OR: mirror mode (makes a *copy* with redactions; originals untouched)
python3 src/redact_secrets.py /path/to/your/project \
  --mirror-out /tmp/project_sanitized
```

4) **Pack** the project:
```bash
# Pack originals
python3 src/pack.py --root /path/to/your/project --force-include templates/

# OR pack the sanitized copy
python3 src/pack.py --root /tmp/project_sanitized --force-include templates/
```

Outputs will appear under:
```
projects_context/<project_name>_context/
```

---

## Use with ChatGPT (or any LLM UI)

In a **new chat**:

1. Upload `projects_context/<project>_context/<project>_context.zip`
    - or upload all files in `chunks/` (in order: 0001.md, 0002.md, …)
2. Paste this starter prompt:

```
I’ve uploaded my full project context as Markdown (repo tree + code).

Instructions:
- Treat this file as my authoritative project context.
- When referring to files, always cite their relative repo paths (e.g., `apps/accounts/views.py`).
- Do not “summarize away” code unless I ask — reason from the actual code provided.
- If you’re unsure about a detail, ask me which file/chunk to open; don’t hallucinate.
- If something isn’t in the context, say so explicitly.

Confirm you’ve loaded the project context and are ready for questions.
```

---

## CLI options

`pack.py`
```
--root PATH            Project root to scan (required)
--out-parent PATH      Parent output dir (default: projects_context)
--project-name NAME    Override output naming (defaults to folder name)
--max-bytes N          Max bytes per chunk (default ~9MB)
--include-exts CSV     File extensions to include (defaults are sensible)
--force-include CSV    Path prefixes to always include (e.g., templates/,docs/)
```

`redact_secrets.py`
```
root                   Project root to scan (required)
--mirror-out PATH      If set, write a redacted copy to this directory
```

**Notes**
- Chunking is UTF-8 safe (won’t break multibyte chars).
- Huge single files are truncated conservatively inside the pack.
- `.gptignore` can exclude large/binary/secrets to save tokens.

---

## FAQ

**I only got `0001.md`. Is that normal?**  
Yes—your project fit under the chunk size. One chunk is perfect.

**Does ChatGPT remember my repo next time?**  
No. Start a fresh chat and re-upload the pack when needed.

**Can I include images or PDFs?**  
Usually skip them—they’re large and not token-efficient. If needed, remove them from `.gptignore` and re-pack.

**I don’t want to modify my source during redaction.**  
Use `--mirror-out` to redact to a copy and pack the copy.

---

## Contributing

PRs welcome! Ideas: dry-run listing, richer redact patterns, tests for ignore rules/chunking behaviors.

## License

MIT (see `LICENSE`).

---
#### Made with ❤️ by Hasan Alani
