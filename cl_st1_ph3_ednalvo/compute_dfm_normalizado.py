#!/usr/bin/env python3
"""
Compute a normalised Document Feature Matrix (DFM) from GELC LLM tagged files.

The programme reads:

1. A tagset Markdown file containing numerical tag definitions, e.g.
   1. artigos definidos
   7.2. determinantes numerais ordinais
   900. todos_artigos

2. A directory of tagged text files where numerical annotations occur inside
   braces, e.g.
   humano {42, 51, 903} é {56, 57, 79, 102, 904}

It writes a TSV matrix with:

    filename    subcorpus    wcount    v001    v002    v007_1    ...    v919

The wcount column contains the number of valid numerical annotation groups in
each document. This corresponds to the number of annotated tokens/words used as
the denominator for normalised frequencies.

By default, counts are normalised per 1,000 annotated tokens. Use --raw-count
to output raw counts.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path


TAGSET_TAG_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\.\s+")
BRACE_RE = re.compile(r"\{([^{}]*)\}")
NUMERIC_TAG_LIST_RE = re.compile(
    r"^\s*\d+(?:\.\d+)?(?:\s*,\s*\d+(?:\.\d+)?)*\s*$"
)


class DFMError(Exception):
    """Raised when the DFM cannot be computed because of invalid input."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute a raw or normalised Document Feature Matrix from "
            "GELC LLM tagged text files."
        )
    )

    parser.add_argument(
        "--input-dir",
        required=True,
        type=Path,
        help="Directory containing tagged .txt/.md files.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help=(
            "Output TSV file path. The option name is kept as --output-dir "
            "to match the project pipeline syntax."
        ),
    )
    parser.add_argument(
        "--tagset",
        required=True,
        type=Path,
        help="Markdown tagset file containing numerical tag definitions.",
    )
    parser.add_argument(
        "--raw-count",
        action="store_true",
        help="Output raw counts instead of counts normalised per 1,000 tokens.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Read tagged files recursively below --input-dir.",
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=[".txt", ".md"],
        help="File extensions to read. Default: .txt .md",
    )

    return parser.parse_args()


def normalise_extension(ext: str) -> str:
    ext = ext.strip()
    if not ext:
        raise DFMError("Empty file extension passed to --extensions.")
    return ext if ext.startswith(".") else f".{ext}"


def tag_sort_key(tag: str) -> tuple[int, int]:
    """
    Sort tags numerically.

    Examples:
        1     -> (1, 0)
        7.1   -> (7, 1)
        7.2   -> (7, 2)
        900   -> (900, 0)
    """
    if "." in tag:
        left, right = tag.split(".", 1)
        return int(left), int(right)
    return int(tag), 0


def tag_to_variable(tag: str) -> str:
    """
    Convert a tagset code to a SAS-safe variable name.

    Examples:
        1   -> v001
        28  -> v028
        900 -> v900
        7.1 -> v007_1
        7.2 -> v007_2
    """
    if "." in tag:
        left, right = tag.split(".", 1)
        return f"v{int(left):03d}_{right}"
    return f"v{int(tag):03d}"


def read_tagset_tags(tagset_path: Path) -> list[str]:
    """Read numerical tag codes from the tagset Markdown file."""
    if not tagset_path.exists():
        raise DFMError(f"Tagset file not found: {tagset_path}")
    if not tagset_path.is_file():
        raise DFMError(f"Tagset path is not a file: {tagset_path}")

    tags: set[str] = set()

    try:
        text = tagset_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise DFMError(f"Could not read tagset as UTF-8: {tagset_path}") from exc

    for line in text.splitlines():
        match = TAGSET_TAG_RE.match(line)
        if match:
            tags.add(match.group(1))

    if not tags:
        raise DFMError(f"No numerical tags found in tagset: {tagset_path}")

    return sorted(tags, key=tag_sort_key)


def iter_input_files(
    input_dir: Path,
    extensions: set[str],
    recursive: bool,
) -> list[Path]:
    """Return tagged files in stable order."""
    if not input_dir.exists():
        raise DFMError(f"Input directory not found: {input_dir}")
    if not input_dir.is_dir():
        raise DFMError(f"Input path is not a directory: {input_dir}")

    pattern = "**/*" if recursive else "*"
    files = [
        path
        for path in input_dir.glob(pattern)
        if path.is_file() and path.suffix.lower() in extensions
    ]

    return sorted(files, key=lambda path: path.name.lower())


def parse_numeric_tag_group(group_text: str) -> list[str] | None:
    """
    Parse one brace group.

    Returns a list of tags if the group is purely numerical, otherwise None.

    Valid:
        {42, 51, 903}
        {7.2}
        {1, 7.1, 900}

    Ignored:
        {FO: auto suficiente}
        {PO: dar}
        {foo}
        {42, FO: x}
    """
    if not NUMERIC_TAG_LIST_RE.fullmatch(group_text):
        return None

    return [part.strip() for part in group_text.split(",")]


def count_tags_in_text(
    text: str,
    allowed_tags: set[str],
) -> tuple[Counter[str], int, Counter[str]]:
    """
    Count tag occurrences in a tagged document.

    The document length used for normalisation is the number of valid numeric
    brace groups. This corresponds to the number of annotated tokens/words.

    Returns:
        counts:
            Counts for tags found in allowed_tags.
        annotated_token_count:
            Number of valid numeric brace groups.
        unknown_counts:
            Numerical tags present in files but absent from the tagset.
    """
    counts: Counter[str] = Counter()
    unknown_counts: Counter[str] = Counter()
    annotated_token_count = 0

    for brace_match in BRACE_RE.finditer(text):
        group_text = brace_match.group(1)
        tags = parse_numeric_tag_group(group_text)

        if tags is None:
            continue

        annotated_token_count += 1

        for tag in tags:
            if tag in allowed_tags:
                counts[tag] += 1
            else:
                unknown_counts[tag] += 1

    return counts, annotated_token_count, unknown_counts


def format_number(value: float) -> str:
    """
    Format numeric values for TSV output.

    Keeps integer-looking values compact while preserving decimals for
    normalised frequencies.
    """
    if value == int(value):
        return str(int(value))

    return f"{value:.6f}".rstrip("0").rstrip(".")


def build_row(
    file_path: Path,
    input_dir: Path,
    tags: list[str],
    counts: Counter[str],
    annotated_token_count: int,
    raw_count: bool,
    recursive: bool,
) -> dict[str, str]:
    """Build one DFM output row."""
    if recursive:
        relative_parent = file_path.parent.relative_to(input_dir)
        if str(relative_parent) == ".":
            subcorpus = input_dir.name
        else:
            subcorpus = str(relative_parent).replace("\\", "/")
    else:
        subcorpus = input_dir.name

    row: dict[str, str] = {
        "filename": file_path.name,
        "subcorpus": subcorpus,
        "wcount": str(annotated_token_count),
    }

    for tag in tags:
        variable = tag_to_variable(tag)
        count = counts.get(tag, 0)

        if raw_count:
            value = float(count)
        elif annotated_token_count > 0:
            value = count / annotated_token_count * 1000
        else:
            value = 0.0

        row[variable] = format_number(value)

    return row


def write_tsv(
    output_path: Path,
    fieldnames: list[str],
    rows: list[dict[str, str]],
) -> None:
    """Write rows to a UTF-8 TSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()

    input_dir = args.input_dir
    output_path = args.output_dir
    tagset_path = args.tagset
    raw_count = args.raw_count
    recursive = args.recursive
    extensions = {normalise_extension(ext).lower() for ext in args.extensions}

    try:
        tags = read_tagset_tags(tagset_path)
        allowed_tags = set(tags)
        input_files = iter_input_files(input_dir, extensions, recursive)

        if not input_files:
            raise DFMError(
                f"No input files found in {input_dir} with extensions: "
                f"{', '.join(sorted(extensions))}"
            )

        variable_names = [tag_to_variable(tag) for tag in tags]
        fieldnames = ["filename", "subcorpus", "wcount", *variable_names]

        rows: list[dict[str, str]] = []
        all_unknown_counts: Counter[str] = Counter()
        files_with_zero_tokens: list[Path] = []

        for file_path in input_files:
            try:
                text = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise DFMError(f"Could not read file as UTF-8: {file_path}") from exc

            counts, annotated_token_count, unknown_counts = count_tags_in_text(
                text=text,
                allowed_tags=allowed_tags,
            )

            if annotated_token_count == 0:
                files_with_zero_tokens.append(file_path)

            all_unknown_counts.update(unknown_counts)

            rows.append(
                build_row(
                    file_path=file_path,
                    input_dir=input_dir,
                    tags=tags,
                    counts=counts,
                    annotated_token_count=annotated_token_count,
                    raw_count=raw_count,
                    recursive=recursive,
                )
            )

        write_tsv(output_path, fieldnames, rows)

        mode = "raw counts" if raw_count else "normalised counts per 1,000 annotated tokens"
        print(f"Wrote DFM: {output_path}")
        print(f"Mode: {mode}")
        print(f"Input files processed: {len(input_files)}")
        print(f"Variables from tagset: {len(tags)}")
        print(f"Subcorpus: {input_dir.name}")

        if files_with_zero_tokens:
            print(
                "Warning: files with zero valid numerical annotation groups:",
                file=sys.stderr,
            )
            for path in files_with_zero_tokens:
                print(f"  - {path}", file=sys.stderr)

        if all_unknown_counts:
            print(
                "Warning: numerical tags found in input files but absent from tagset:",
                file=sys.stderr,
            )
            for tag, count in sorted(
                all_unknown_counts.items(),
                key=lambda item: tag_sort_key(item[0]),
            ):
                print(f"  - {tag}: {count}", file=sys.stderr)

        return 0

    except DFMError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())