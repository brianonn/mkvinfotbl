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

