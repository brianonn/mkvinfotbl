# mkvinfotbl

Parses the text output of `mkvinfo` and renders it as human-readable ASCII tables. No third-party dependencies — standard library only.

## Background

`mkvinfo` (part of the [MKVToolNix](https://mkvtoolnix.download/) suite) dumps the internal structure of a Matroska (`.mkv`) file as a deeply-nested tree of key/value pairs, for example:

```
+ EBML head
|+ EBML version: 1
|+ Tracks
| + Track
|  + Track number: 1 (track ID for mkvmerge & mkvextract: 0)
|  + Track type: video
|  + Video track
|   + Pixel width: 3832
```

Reading this raw output for files with many tracks is tedious. `mkvinfotbl` parses the tree and renders three focused tables:

| Table | Contents |
|---|---|
| **EBML Head** | Container format version fields |
| **Segment Information** | Duration, muxer/writer app, segment UID |
| **Tracks** | One row per track — type, codec, language, resolution/sample rate, accessibility flags |

### Example output

```
+=======================================+
|               EBML Head               |
+----------------------------+----------+
| Field                      | Value    |
+----------------------------+----------+
| EBML version               | 1        |
| Document type              | matroska |
| Document type version      | 4        |
+----------------------------+----------+

+============================================================================+
|                            Segment Information                             |
+--------------------------+-------------------------------------------------+
| Field                    | Value                                           |
+--------------------------+-------------------------------------------------+
| Duration                 | 01:52:56.000000000                              |
| Writing application      | mkvmerge v97.0 ('You Don't Have A Clue') 64-bit |
+--------------------------+-------------------------------------------------+

+=====================================================================+
|                               Tracks                                |
+----+-----------+------------------+-----------------+----------+----+
| #  | Type      | Codec            | Language (IETF) | Language | …  |
+----+-----------+------------------+-----------------+----------+----+
| 1  | video     | V_MPEGH/ISO/HEVC | und             | und      | …  |
| 2  | audio     | A_EAC3           | en              |          | …  |
| 3  | subtitles | S_TEXT/UTF8      | en-US           |          | …  |
+----+-----------+------------------+-----------------+----------+----+
```

## Requirements

- Python 3.10+ (uses `list[...]` type hints without `from __future__ import annotations`)
- `mkvinfo` installed and on `$PATH` (provided by [MKVToolNix](https://mkvtoolnix.download/))

No `pip install` required — only `sys`, `re`, and `dataclasses` from the standard library are used.

## Usage

**Pipe directly from mkvinfo (most common):**
```bash
mkvinfo movie.mkv | python3 mkvinfotbl.py
```

**From a saved file:**
```bash
python3 mkvinfotbl.py mkvinfo_output.txt
```

**Redirect stdin explicitly:**
```bash
python3 mkvinfotbl.py < mkvinfo_output.txt
```

**Save output to a file:**
```bash
mkvinfo movie.mkv | python3 mkvinfotbl.py > summary.txt
```

## Code structure

The script is intentionally kept as a single file with no external dependencies. It is organised into five layers, top to bottom:

```
parse_line()          raw text → Node (depth + key/value)
parse_mkvinfo()       lines → flat list[Node]
build_tree()          flat list → parent/child tree
tree helpers          child_value(), nested_child_value(), find_nodes_by_key()
table builders        ebml_head_table(), segment_info_table(), tracks_table()
ascii_table()         generic renderer used by all table builders
main()                I/O wiring
```

### The `Node` dataclass

```python
@dataclass
class Node:
    depth: int
    key:   str
    value: str
    children: list[Node]
```

Every line in the `mkvinfo` output becomes one `Node`. After `build_tree()`, each node holds its direct children, giving you a navigable tree that mirrors the original structure.

### Depth encoding

The key non-obvious detail in the parser: `mkvinfo` encodes depth via the **length of the prefix before `+`**, not by counting `|` characters. Siblings and children at the same visual nesting level can share the same number of `|` characters:

```
|+ Tracks          prefix="|"   depth=1  (1 pipe, no spaces)
| + Track          prefix="| "  depth=2  (1 pipe + 1 space)
|  + Track number  prefix="|  " depth=3  (1 pipe + 2 spaces)
|   + Pixel width  prefix="|   " depth=4 (1 pipe + 3 spaces)
```

`parse_line()` uses `line.find('+')` as the depth value directly — the index of `+` equals the prefix length.

### Tree building

`build_tree()` uses a single stack pass (O(n)). The invariant: `stack[-1]` is always the deepest currently-open node. When a new node arrives at depth N, everything on the stack at depth ≥ N is popped before the new node is attached to the new top. No recursion.

### Adding a new table

Adding a new output section is a three-step pattern:

1. **Find the section root** using `find_nodes_by_key(roots, "Section name")`.
2. **Extract fields** using `child_value(node, "Field name")` or `nested_child_value(node, "Parent", "Child")` for nested data.
3. **Render** by calling `ascii_table("Title", ["Col1", "Col2", ...], rows)`.

Example — adding a Chapters table:

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

Then add `print(chapters_table(roots))` in `main()`.

### The `ascii_table()` renderer

Accepts a title string, a list of header strings, and a list of rows (each row is a `list[str]`). Column widths are auto-sized to the widest value in each column. The title bar uses `=` separators and is derived from `len(sep)` rather than independently calculated, which avoids off-by-one alignment bugs.

```
+====================+     <- title_sep: "+" + "=" * (len(sep)-2) + "+"
|       Title        |     <- title centred in (len(sep)-4) chars
+--------+-----------+     <- sep: column separators
| Field  | Value     |     <- header row
+--------+-----------+
| foo    | bar       |     <- data rows
+--------+-----------+
```

## Known limitations

- Only three sections are rendered (EBML head, segment info, tracks). Chapters, attachments, tags, and cue points are parsed into the tree but not yet presented.
- The `Extra` column in the Tracks table is a comma-separated catch-all. For files with many flags, it can get wide.
- `mkvinfo -v` (verbose) produces additional sub-fields not covered by the current table builders; they will be silently ignored rather than causing errors.
- Output is plain ASCII, not colour-coded. Piping through `less -S` is recommended for wide tables.

## Potential improvements

- `--section` flag to select which tables to print
- `--json` output mode (the tree is already in memory, it just needs a serialiser)
- Colour output via ANSI codes when writing to a TTY
- Chapter and attachment table builders following the pattern above
- `pip`-installable package with a `mkvinfotbl` entry point
