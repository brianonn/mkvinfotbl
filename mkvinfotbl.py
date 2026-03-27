#!/usr/bin/env python3
"""
mkvinfotbl.py - Parse mkvinfo output and render ASCII tables.

Usage:
    mkvinfo <file.mkv> | python3 mkvinfotbl.py
    python3 mkvinfotbl.py < mkvinfo_output.txt
    python3 mkvinfotbl.py mkvinfo_output.txt
"""

import sys
import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Node:
    """A single line from mkvinfo with its depth and parsed key/value."""
    depth: int
    key: str
    value: str
    children: list["Node"] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_line(line: str) -> Optional[Node]:
    """
    Parse one mkvinfo output line into a Node.

    mkvinfo uses '|' and '+' characters to show hierarchy.  The depth of a
    node equals the length of the prefix before the '+' character:

        prefix ""    -> depth 0   (top-level)   e.g.  "+ EBML head"
        prefix "|"   -> depth 1                 e.g.  "|+ Tracks"
        prefix "| "  -> depth 2                 e.g.  "| + Track"
        prefix "|  " -> depth 3                 e.g.  "|  + Track number: 1"
        prefix "|   "-> depth 4                 e.g.  "|   + Pixel width: 3832"

    Using prefix length (not pipe count) correctly distinguishes siblings
    from children even when they share the same number of '|' characters.
    """
    stripped = line.rstrip()
    if not stripped:
        return None

    plus_idx = stripped.find('+')
    if plus_idx == -1:
        return None

    depth = plus_idx                    # length of prefix = depth
    content = stripped[plus_idx + 1:].strip()
    if not content:
        return None

    # Split on first ': ' to separate key from value
    if ': ' in content:
        key, _, value = content.partition(': ')
    else:
        key, value = content, ''

    return Node(depth=depth, key=key.strip(), value=value.strip())


def parse_mkvinfo(text: str) -> list[Node]:
    """Parse full mkvinfo text into a flat list of depth-annotated Nodes."""
    nodes = []
    for line in text.splitlines():
        node = parse_line(line)
        if node is not None:
            nodes.append(node)
    return nodes


def build_tree(flat: list[Node]) -> list[Node]:
    """
    Convert the flat depth-annotated list into a proper parent/child tree.
    Returns only the top-level root nodes.

    Think of it like a stack of open folders: when we encounter a node at
    depth N, we close every open folder at depth >= N, then attach this node
    to whatever folder is currently on top.
    """
    roots: list[Node] = []
    stack: list[Node] = []

    for node in flat:
        while stack and stack[-1].depth >= node.depth:
            stack.pop()

        if stack:
            stack[-1].children.append(node)
        else:
            roots.append(node)

        stack.append(node)

    return roots


# ---------------------------------------------------------------------------
# Tree helpers
# ---------------------------------------------------------------------------

def find_nodes_by_key(nodes: list[Node], key: str, recursive: bool = True) -> list[Node]:
    """Return all nodes whose key matches (case-insensitive)."""
    results = []
    for n in nodes:
        if n.key.lower() == key.lower():
            results.append(n)
        if recursive:
            results.extend(find_nodes_by_key(n.children, key, recursive))
    return results


def child_value(node: Node, key: str) -> str:
    """Return the value of the first direct child whose key matches, or ''."""
    key_l = key.lower()
    for c in node.children:
        if c.key.lower() == key_l:
            return c.value
    return ''


def nested_child_value(node: Node, *keys: str) -> str:
    """
    Walk a chain of nested children and return the final value.

    Example: nested_child_value(track_node, 'Video track', 'Pixel width')
    """
    current = node
    for key in keys:
        found = None
        for c in current.children:
            if c.key.lower() == key.lower():
                found = c
                break
        if found is None:
            return ''
        current = found
    return current.value


# ---------------------------------------------------------------------------
# ASCII table renderer
# ---------------------------------------------------------------------------

def ascii_table(title: str, headers: list[str], rows: list[list[str]]) -> str:
    """Render a plain ASCII table with a centred title header."""
    if not rows:
        return f"  [{title}: no data]\n"

    # Compute column widths from headers and all cell values
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    def fmt_row(cells: list[str]) -> str:
        parts = [str(c).ljust(col_widths[i] if i < len(col_widths) else len(str(c)))
                 for i, c in enumerate(cells)]
        return "| " + " | ".join(parts) + " |"

    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    inner_width = sum(col_widths) + 3 * len(col_widths) - 1
    title_sep = "+" + "=" * (inner_width + 2) + "+"
    title_line = "| " + title.center(inner_width) + " |"

    lines = [title_sep, title_line, sep, fmt_row(headers), sep]
    for row in rows:
        lines.append(fmt_row(row))
    lines.append(sep)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def ebml_head_table(roots: list[Node]) -> str:
    nodes = find_nodes_by_key(roots, "EBML head")
    if not nodes:
        return "  [EBML head: not found]\n"
    ebml = nodes[0]
    rows = [[c.key, c.value] for c in ebml.children if c.value]
    return ascii_table("EBML Head", ["Field", "Value"], rows)


def segment_info_table(roots: list[Node]) -> str:
    nodes = find_nodes_by_key(roots, "Segment information")
    if not nodes:
        return "  [Segment information: not found]\n"
    info = nodes[0]
    fields = [
        "Timestamp scale",
        "Duration",
        "Multiplexing application",
        "Writing application",
        "Segment UID",
    ]
    rows = [[f, child_value(info, f)] for f in fields if child_value(info, f)]
    return ascii_table("Segment Information", ["Field", "Value"], rows)


def tracks_table(roots: list[Node]) -> str:
    track_nodes = find_nodes_by_key(roots, "Track")
    if not track_nodes:
        return "  [Tracks: not found]\n"

    headers = ["#", "Type", "Codec", "Language (IETF)", "Language", "Name", "Extra"]
    rows = []

    for t in track_nodes:
        num_raw = child_value(t, "Track number")
        # "1 (track ID for mkvmerge & mkvextract: 0)" -> just the number
        num = num_raw.split()[0] if num_raw else ""

        ttype     = child_value(t, "Track type")
        codec     = child_value(t, "Codec ID")
        lang_ietf = child_value(t, "Language (IETF BCP 47)")
        lang      = child_value(t, "Language")
        name      = child_value(t, "Name")

        extra_parts = []

        # Video: resolution
        pw = nested_child_value(t, "Video track", "Pixel width")
        ph = nested_child_value(t, "Video track", "Pixel height")
        if pw and ph:
            extra_parts.append(f"{pw}x{ph}px")

        # Video: codec profile from private data annotation "(HEVC profile: ...)"
        codec_priv = child_value(t, "Codec's private data")
        if codec_priv:
            m = re.search(r'\(([^)]+)\)', codec_priv)
            if m:
                extra_parts.append(m.group(1))

        # Audio: sample rate + channels
        sf = nested_child_value(t, "Audio track", "Sampling frequency")
        ch = nested_child_value(t, "Audio track", "Channels")
        if sf:
            extra_parts.append(f"{sf}Hz")
        if ch:
            extra_parts.append(f"{ch}ch")

        # Accessibility / language flags
        for flag_key, flag_label in [
            ('"Hearing impaired" flag',  "HI"),
            ('"Visual impaired" flag',   "VI"),
            ('"Original language" flag', "OrgLang"),
        ]:
            if child_value(t, flag_key) == "1":
                extra_parts.append(flag_label)

        rows.append([num, ttype, codec, lang_ietf, lang, name, ", ".join(extra_parts)])

    return ascii_table("Tracks", headers, rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    flat = parse_mkvinfo(text)
    roots = build_tree(flat)

    print()
    print(ebml_head_table(roots))
    print(segment_info_table(roots))
    print(tracks_table(roots))


if __name__ == "__main__":
    main()
