#!/usr/bin/env python3
"""
project_scanner.py

A tiny utility that walks a directory tree and prints a summary of its contents.
It shows a tree view, counts files/directories, totals file size, and reports
the most common file extensions.

Usage
-----
    python project_scanner.py [directory]

If *directory* is omitted the current working directory is scanned.
"""

from __future__ import annotations

import argparse
import collections
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Counter, Iterable, List, Tuple


# --------------------------------------------------------------------------- #
# Helper data structures
# --------------------------------------------------------------------------- #
@dataclass
class ScanResult:
    """Container for all statistics gathered while scanning a directory."""
    total_files: int = 0
    total_dirs: int = 0
    total_size_bytes: int = 0
    ext_counter: Counter[str] = field(default_factory=collections.Counter)
    tree_lines: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Core scanning logic
# --------------------------------------------------------------------------- #
def _human_readable_size(num_bytes: int) -> str:
    """
    Convert a size in bytes to a human‑readable string (KB, MB, GB …).

    Parameters
    ----------
    num_bytes: int
        Size in bytes.

    Returns
    -------
    str
        Human readable representation, e.g. "1.23 MiB".
    """
    # Use binary prefixes (KiB = 1024 B) – they are the most common for source code.
    step = 1024
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    size = float(num_bytes)
    for unit in units:
        if size < step:
            return f"{size:.2f} {unit}"
        size /= step
    return f"{size:.2f} {units[-1]}"


def _add_tree_line(
    lines: List[str],
    prefix: str,
    name: str,
    is_last: bool,
    is_dir: bool,
) -> None:
    """
    Append a formatted line to the tree view.

    Parameters
    ----------
    lines: List[str]
        The list that stores the tree lines.
    prefix: str
        The accumulated prefix (e.g. "│   ├── ").
    name: str
        File or directory name.
    is_last: bool
        Whether this entry is the last child of its parent.
    is_dir: bool
        True if the entry is a directory (adds a trailing slash).
    """
    connector = "└── " if is_last else "├── "
    display_name = f"{name}/" if is_dir else name
    lines.append(f"{prefix}{connector}{display_name}")


def scan_directory(root: Path) -> ScanResult:
    """
    Walk *root* recursively and collect statistics.

    Parameters
    ----------
    root: pathlib.Path
        Directory to scan.

    Returns
    -------
    ScanResult
        All gathered information.
    """
    if not root.is_dir():
        raise NotADirectoryError(f"{root!s} is not a directory")

    result = ScanResult()
    # The stack holds tuples: (path, prefix, is_last_child)
    # ``prefix`` is the string that should be printed before the entry.
    stack: List[Tuple[Path, str, bool]] = [(root, "", True)]

    while stack:
        current_path, prefix, is_last = stack.pop()
        # ``current_path`` is a directory – we already know it exists.
        result.total_dirs += 1
        _add_tree_line(
            result.tree_lines,
            prefix,
            current_path.name,
            is_last,
            is_dir=True,
        )

        # Gather children sorted alphabetically for deterministic output.
        try:
            children = sorted(current_path.iterdir(), key=lambda p: p.name.lower())
        except PermissionError:
            # Skip directories we cannot read.
            result.tree_lines.append(f"{prefix}    [Permission denied]")
            continue

        # Build the prefix for the next level.
        if prefix == "":
            child_prefix = "    "
        else:
            # Replace the connector of the current line with the appropriate vertical bar.
            child_prefix = prefix + ("    " if is_last else "│   ")

        # Process children in reverse order so that the left‑most child is popped last
        # (i.e. printed first) – this mimics the behaviour of the classic `tree` command.
        for idx, child in enumerate(reversed(children)):
            child_is_last = idx == 0  # because we reversed the list
            if child.is_dir():
                # Push directories onto the stack to be processed later.
                stack.append((child, child_prefix, child_is_last))
            else:
                # Files are leaf nodes – handle them immediately.
                result.total_files += 1
                result.total_size_bytes += child.stat().st_size
                ext = child.suffix.lower() or "<no_ext>"
                result.ext_counter[ext] += 1
                _add_tree_line(
                    result.tree_lines,
                    child_prefix,
                    child.name,
                    child_is_last,
                    is_dir=False,
                )

    return result


# --------------------------------------------------------------------------- #
# Presentation helpers
# --------------------------------------------------------------------------- #
def _print_report(res: ScanResult, root: Path) -> None:
    """
    Print a human‑readable report based on the scan result.

    Parameters
    ----------
    res: ScanResult
        The data collected by ``scan_directory``.
    root: pathlib.Path
        The scanned root directory (used for the header).
    """
    print(f"\nScanning project: {root.resolve()}\n")
    print("\n".join(res.tree_lines))
    print("\n--- Summary -----------------------------------------------------------")
    print(f"Directories : {res.total_dirs}")
    print(f"Files       : {res.total_files}")
    print(f"Total size  : {_human_readable_size(res.total_size_bytes)}")
    print("\nTop file extensions:")
    for ext, count in res.ext_counter.most_common(10):
        print(f"  {ext:>8} : {count}")
    print("-----------------------------------------------------------------------\n")


# --------------------------------------------------------------------------- #
# CLI entry point
# --------------------------------------------------------------------------- #
def build_arg_parser() -> argparse.ArgumentParser:
    """Create the command‑line argument parser."""
    parser = argparse.ArgumentParser(
        description="Recursively scan a directory and print a concise report.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        type=Path,
        help="Root directory of the project to scan (default: current directory).",
    )
    return parser


def main(argv: List[str] | None = None) -> int:
    """Entry point for the script."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        result = scan_directory(args.path.resolve())
    except Exception as exc:  # pragma: no cover – defensive, unlikely to be hit in tests
        print(f"Error while scanning: {exc}", file=sys.stderr)
        return 1

    _print_report(result, args.path)
    return 0


if __name__ == "__main__":
    sys.exit(main())