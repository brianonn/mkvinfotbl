# TASKS

Tracked improvements and known work items for `mkvinfotbl`. Items are grouped by theme. Dependencies between tasks are noted inline.

---

## CLI

### T-01 — `--section` flag to select which tables to print
**Status:** Open

Allow the user to request only specific output sections rather than always printing all three.

```bash
mkvinfotbl.py movie.mkv --section tracks
mkvinfotbl.py movie.mkv --section ebml --section segment
```

Suggested implementation: `argparse` with `--section` as a repeatable argument. If omitted, default to all sections. Each table builder is already a standalone function so wiring this up is straightforward.

---

### T-02 — Accept `.mkv` filename directly; invoke `mkvinfo` internally
**Status:** Open

Currently the user must pipe `mkvinfo` output manually:
```bash
mkvinfo movie.mkv | python3 mkvinfotbl.py
```

This task makes `mkvinfotbl` accept an `.mkv` file path as the first argument and shell out to `mkvinfo` itself:
```bash
python3 mkvinfotbl.py movie.mkv
```

Suggested implementation:
- Detect whether `sys.argv[1]` ends in `.mkv` (or similar media extension).
- Use `subprocess.run(["mkvinfo", path], capture_output=True, text=True)` to capture the output.
- Feed the resulting stdout string into the existing `parse_mkvinfo()` pipeline — no other changes needed.
- Return a clear error if `mkvinfo` is not found on `$PATH` (`FileNotFoundError` from `subprocess`).
- Keep the stdin/file-path fallback paths working for users who prefer to pipe.

---

## Output formats

### T-03 — `--json` output mode
**Status:** Open  
**Blocks:** T-04

The in-memory `Node` tree is already fully structured — it just needs a serialiser. A `--json` flag should dump the entire parsed tree (or the same sections selected by T-01) as JSON to stdout.

```bash
mkvinfo movie.mkv | python3 mkvinfotbl.py --json
mkvinfo movie.mkv | python3 mkvinfotbl.py --json --section tracks
```

Suggested implementation: a recursive `node_to_dict(node: Node) -> dict` function, then `json.dumps(..., indent=2)`. No third-party libraries needed.

---

### T-04 — `--csv` output mode
**Status:** Open  
**Blocked by:** T-03

CSV output is best implemented on top of the JSON representation (T-03) rather than directly from the `Node` tree, since JSON → CSV flattening is well-understood and keeps the logic in one place.

Each section (tracks, segment info, etc.) would produce its own CSV block or separate file. The Tracks table maps cleanly to CSV rows; EBML Head and Segment Information are key/value pairs that can emit as two-column CSV.

```bash
mkvinfo movie.mkv | python3 mkvinfotbl.py --csv --section tracks > tracks.csv
```

---

### T-05 — Colour output via ANSI codes when writing to a TTY
**Status:** Open

When stdout is a terminal (`sys.stdout.isatty()`), apply ANSI colour codes to improve scannability — e.g. bold headers, coloured track-type column (`video` in blue, `audio` in green, `subtitles` in yellow). When piped or redirected, emit plain text as today.

No third-party libraries needed; raw ANSI escape codes are sufficient. Alternatively, the stdlib `curses` module can be used for portability.

---

## New table sections

### T-06 — Chapter table builder
**Status:** Open

Chapters are already parsed into the `Node` tree but not rendered. Add a `chapters_table()` function following the same pattern as the existing table builders.

Relevant `mkvinfo` keys: `Chapter atom`, `Chapter UID`, `Chapter time start`, `Chapter time end`, `Chapter display` → `Chapter string`.

Example skeleton:
```python
def chapters_table(roots: list[Node]) -> str:
    chapter_atoms = find_nodes_by_key(roots, "Chapter atom")
    if not chapter_atoms:
        return "  [Chapters: not found]\n"
    rows = []
    for atom in chapter_atoms:
        uid   = child_value(atom, "Chapter UID")
        start = child_value(atom, "Chapter time start")
        name  = nested_child_value(atom, "Chapter display", "Chapter string")
        rows.append([uid, start, name])
    return ascii_table("Chapters", ["UID", "Start", "Name"], rows)
```

---

### T-07 — Attachment table builder
**Status:** Open

MKV files can carry embedded attachments (fonts, cover art, ICC profiles). Add an `attachments_table()` function.

Relevant `mkvinfo` keys: `Attached`, `File name`, `File MIME type`, `File data`, `File UID`.

---

## Packaging

### T-08 — `pip`-installable package with a `mkvinfotbl` entry point
**Status:** Open  
**Suggested order:** Implement after T-01 and T-02 stabilise the CLI interface.

Add a minimal `pyproject.toml` so the tool can be installed via:
```bash
pip install .
mkvinfotbl movie.mkv
```

Minimum viable `pyproject.toml`:
```toml
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "mkvinfotbl"
version = "0.1.0"
requires-python = ">=3.10"

[project.scripts]
mkvinfotbl = "mkvinfotbl:main"
```

---

## Suggested implementation order

```
T-02  (direct .mkv arg)          quick win, self-contained
T-01  (--section flag)           needed before packaging
T-05  (colour TTY output)        self-contained, no deps on other tasks
T-06  (chapters table)           self-contained, follows existing pattern
T-07  (attachments table)        self-contained, follows existing pattern
T-03  (--json output)            unlocks T-04
T-04  (--csv output)             requires T-03
T-08  (pip package)              last, after CLI is stable
```
