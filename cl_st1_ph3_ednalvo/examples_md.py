#!/usr/bin/env python3
"""
Generate Markdown example texts for Phase 3 TMDA factor-pole interpretation.

For each factor dimension (f1, f2, etc.):
    - Calculate the mean score for each subcorpus.
    - Positive pole: subcorpora ranked by descending mean factor score.
    - Negative pole: subcorpora ranked by ascending mean factor score.
    - Top-ranked subcorpus: more examples.
    - Other subcorpora: fewer examples each.
    - Skip any text where the factor score == 0.

The programme is adapted for the cl_st1_ph3_ednalvo project structure.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import pandas as pd


# =============================================================================
# DEFAULTS
# =============================================================================

DEFAULT_PROJECT = Path.cwd().name
DEFAULT_CORPUS_DIR = Path("corpus") / "01_composicoes"
DEFAULT_OUTPUT_DIR = Path("examples_md")
DEFAULT_LOADTABLE_FILENAME = "loadtable_for_interpretation.csv"

SUPPORTED_TEXT_SUFFIXES = (".txt", ".md", ".markdown")
MARKDOWN_COMPOSITION_HEADING = "Redação"


# =============================================================================
# ARGUMENTS
# =============================================================================

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate Markdown example files for Phase 3 TMDA factor poles."
    )

    parser.add_argument(
        "--project",
        default=DEFAULT_PROJECT,
        help="Project name. Default: current directory name.",
    )
    parser.add_argument(
        "--sas-output-dir",
        default=None,
        help="Directory containing SAS outputs. Default: sas/output_<project>.",
    )
    parser.add_argument(
        "--scores-file",
        default=None,
        help="Scores CSV file. Default: <sas-output-dir>/<project>_scores_only.csv.",
    )
    parser.add_argument(
        "--corpus-dir",
        default=str(DEFAULT_CORPUS_DIR),
        help="Root directory containing composition subcorpora. Default: corpus/01_composicoes.",
    )
    parser.add_argument(
        "--loadtable-file",
        default=None,
        help=(
            "CSV file containing factor-pole loading features. "
            "Default: <sas-output-dir>/loadtable_for_interpretation.csv."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where example Markdown files will be written. Default: examples_md.",
    )
    parser.add_argument(
        "--top-subcorpus-examples",
        type=int,
        default=20,
        help="Number of examples for the top-ranked subcorpus.",
    )
    parser.add_argument(
        "--other-subcorpus-examples",
        type=int,
        default=10,
        help="Number of examples for each other subcorpus.",
    )
    parser.add_argument(
        "--include-secondary-loadings",
        action="store_true",
        help="Include both primary and secondary loadings from the loadtable.",
    )

    return parser.parse_args()


def resolve_sas_output_dir(project: str, sas_output_dir_arg: str | None) -> Path:
    """Resolve the SAS output directory."""
    if sas_output_dir_arg is None:
        return Path("sas") / f"output_{project}"
    return Path(sas_output_dir_arg)


def resolve_scores_file(
        project: str,
        sas_output_dir: Path,
        scores_file_arg: str | None,
) -> Path:
    """Resolve the factor-scores file path."""
    if scores_file_arg is None:
        return sas_output_dir / f"{project}_scores_only.csv"
    return Path(scores_file_arg)


def resolve_loadtable_file(
        sas_output_dir: Path,
        loadtable_file_arg: str | None,
) -> Path:
    """Resolve the factor loadtable CSV path."""
    if loadtable_file_arg is None:
        return sas_output_dir / DEFAULT_LOADTABLE_FILENAME
    return Path(loadtable_file_arg)


# =============================================================================
# HELPERS
# =============================================================================

def natural_sort_key(value: str) -> list[Any]:
    """Return a natural-sort key that treats digit runs as integers."""
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", value)
    ]


def relpath(path: Path, base_dir: Path = Path.cwd()) -> str:
    """Return a path relative to base_dir when possible."""
    try:
        return path.resolve().relative_to(base_dir.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def detect_factor_columns(scores_df: pd.DataFrame) -> list[str]:
    """Detect factor-score columns named f1, f2, etc."""
    factor_columns = [
        str(column)
        for column in scores_df.columns
        if re.fullmatch(r"f\d+", str(column))
    ]

    if not factor_columns:
        raise RuntimeError("No f<n> columns found in scores CSV file.")

    return sorted(factor_columns, key=natural_sort_key)


def table_label_to_factor_pole(table_value: str) -> str | None:
    """
    Convert SAS loadtable labels such as f1pos or f1neg to f1_pos or f1_neg.
    """
    match = re.fullmatch(r"(f\d+)(pos|neg)", str(table_value).strip().lower())
    if not match:
        return None

    return f"{match.group(1)}_{match.group(2)}"


def load_tagset_features(tagset_file: Path | None) -> dict[str, str]:
    """
    Optionally parse tagset feature descriptions.

    This is intentionally optional. If the tagset file is absent, the programme
    still writes feature codes from the SAS loadtable.
    """
    if tagset_file is None or not tagset_file.exists():
        return {}

    feature_lookup: dict[str, str] = {}
    pattern = re.compile(r"^\s*(\d+(?:\.\d+)?)\.\s+(.+?)\s*$")

    for line in tagset_file.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if not match:
            continue

        raw_code = match.group(1)
        description = match.group(2).strip()
        if "." in raw_code:
            code = f"v{raw_code.replace('.', '_')}"
        else:
            code = f"v{int(raw_code):03d}"

        feature_lookup[code] = description

    return feature_lookup


def parse_loadtable(
        loadtable_file: Path,
        *,
        include_secondary: bool,
        feature_descriptions: dict[str, str],
) -> dict[str, list[str]]:
    """
    Parse loadtable_for_interpretation.csv into a factor-pole feature lookup.

    Expected columns:
        type,_NAME_,loading,table

    The table column uses labels such as:
        f1pos
        f1neg

    These are converted to:
        f1_pos
        f1_neg
    """
    if not loadtable_file.exists():
        raise FileNotFoundError(f"Loadtable CSV file not found: {loadtable_file}")

    loadings_df = pd.read_csv(loadtable_file)

    required_columns = {"type", "_NAME_", "loading", "table"}
    missing_columns = required_columns - set(loadings_df.columns)
    if missing_columns:
        raise ValueError(
            f"{loadtable_file} is missing required columns: "
            f"{', '.join(sorted(missing_columns))}"
        )

    if not include_secondary:
        loadings_df = loadings_df[loadings_df["type"].astype(str).str.lower() == "primary"]

    features_lookup: dict[str, list[str]] = {}

    for _, row in loadings_df.iterrows():
        label = table_label_to_factor_pole(str(row["table"]))
        if label is None:
            continue

        feature_code = str(row["_NAME_"]).strip()
        loading = float(row["loading"])
        description = feature_descriptions.get(feature_code)

        if description:
            feature_label = f"{feature_code} ({loading:.3f}; {description})"
        else:
            feature_label = f"{feature_code} ({loading:.3f})"

        features_lookup.setdefault(label, []).append(feature_label)

    return features_lookup


def source_path_candidates(subcorpus: str, filename: str, corpus_dir: Path) -> list[Path]:
    """
    Return possible source-text paths for a scored item.

    The scores file stores generated compositions as .txt because the annotated
    output is .txt, but source generated compositions may be .md or .markdown.
    """
    base_path = corpus_dir / subcorpus / filename
    candidates = [base_path]

    if base_path.suffix.lower() == ".txt":
        stem_path = base_path.with_suffix("")
        candidates.extend(stem_path.with_suffix(suffix) for suffix in (".md", ".markdown"))

    return candidates


def get_full_text_path(subcorpus: str, filename: str, corpus_dir: Path) -> Path | None:
    """Resolve the source text path for a scored composition."""
    for candidate in source_path_candidates(subcorpus, filename, corpus_dir):
        if candidate.exists():
            return candidate

    return None


def extract_markdown_section(markdown_text: str, heading: str) -> str:
    """
    Extract contents under a level-2 Markdown heading until the next level-2 heading.

    For generated compositions, this extracts the actual essay under:

        ## Redação
    """
    heading_pattern = re.compile(
        rf"^##[ \t]+{re.escape(heading)}[ \t]*#*[ \t]*$",
        flags=re.MULTILINE,
    )

    match = heading_pattern.search(markdown_text)
    if not match:
        return markdown_text.strip()

    section_start = match.end()

    next_heading_pattern = re.compile(
        r"^##[ \t]+.+$",
        flags=re.MULTILINE,
    )
    next_match = next_heading_pattern.search(markdown_text, section_start)

    if next_match:
        return markdown_text[section_start:next_match.start()].strip()

    return markdown_text[section_start:].strip()


def read_source_text(path: Path) -> str:
    """Read a source composition, extracting only ## Redação from Markdown files."""
    raw_text = path.read_text(encoding="utf-8", errors="ignore")

    if path.suffix.lower() in {".md", ".markdown"}:
        return extract_markdown_section(raw_text, MARKDOWN_COMPOSITION_HEADING)

    return raw_text.strip()


def write_md_example(
        out_file: Path,
        *,
        subcorpus: str,
        filename: str,
        filepath: Path,
        score: float,
        label: str,
        features: list[str],
        raw_text: str,
) -> None:
    """Write one Markdown example file."""
    features_str = ", ".join(features)

    content = (
        f"**Subcorpus:** {subcorpus}  \n"
        f"**Filename:** {filename}  \n"
        f"**Filepath:** {relpath(filepath)}  \n"
        f"**Score ({label}):** {score:.2f}  \n"
        f"**Loading features ({label}), N={len(features)}:** {features_str}  \n\n"
        f"---\n\n"
        f"{raw_text.rstrip()}\n"
    )

    out_file.write_text(content, encoding="utf-8")


def write_selected_examples_for_subcorpus(
        *,
        rows_df: pd.DataFrame,
        factor_column: str,
        quota: int,
        label: str,
        out_dir: Path,
        start_example_id: int,
        corpus_dir: Path,
        features: list[str],
        missing_files: set[str],
) -> int:
    """Write selected examples for one factor pole and one subcorpus."""
    example_id = start_example_id
    count = 0

    for _, row in rows_df.iterrows():
        if count >= quota:
            break

        score = float(row[factor_column])
        if score == 0:
            continue

        filename = str(row["filename"]).strip()
        subcorpus = str(row["subcorpus"]).strip()

        raw_text_path = get_full_text_path(subcorpus, filename, corpus_dir)
        if raw_text_path is None:
            missing_files.add(str(corpus_dir / subcorpus / filename))
            continue

        raw_text = read_source_text(raw_text_path)
        if not raw_text.strip():
            missing_files.add(f"{raw_text_path} [empty text after extraction]")
            continue

        out_file = out_dir / f"{label}_{example_id:03d}.md"
        write_md_example(
            out_file,
            subcorpus=subcorpus,
            filename=filename,
            filepath=raw_text_path,
            score=score,
            label=label,
            features=features,
            raw_text=raw_text,
        )

        count += 1
        example_id += 1

    return example_id


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    """Generate Markdown example extracts for all factors and poles."""
    args = parse_args()

    project = args.project
    sas_output_dir = resolve_sas_output_dir(project, args.sas_output_dir)
    scores_file = resolve_scores_file(project, sas_output_dir, args.scores_file)
    corpus_dir = Path(args.corpus_dir)
    loadtable_file = resolve_loadtable_file(sas_output_dir, args.loadtable_file)
    output_dir = Path(args.output_dir)

    tagset_file = Path("gelc_llm_taggers") / "tagset_ptbr.md"

    if not scores_file.exists():
        raise FileNotFoundError(f"Scores CSV file not found: {scores_file}")

    if not corpus_dir.exists():
        raise FileNotFoundError(f"Corpus directory not found: {corpus_dir}")

    scores_df = pd.read_csv(scores_file)

    required_columns = {"filename", "subcorpus"}
    missing_columns = required_columns - set(scores_df.columns)
    if missing_columns:
        raise ValueError(
            f"{scores_file} is missing required columns: "
            f"{', '.join(sorted(missing_columns))}"
        )

    factor_columns = detect_factor_columns(scores_df)

    feature_descriptions = load_tagset_features(tagset_file)
    loading_features_lookup = parse_loadtable(
        loadtable_file,
        include_secondary=args.include_secondary_loadings,
        feature_descriptions=feature_descriptions,
    )

    print(f"Project: {project}")
    print(f"Scores file: {scores_file}")
    print(f"Corpus dir: {corpus_dir}")
    print(f"Loadtable: {loadtable_file}")
    print(f"Detected {len(factor_columns)} factors: {', '.join(factor_columns)}.\n")

    output_dir.mkdir(exist_ok=True, parents=True)
    missing_files: set[str] = set()

    means_df = scores_df.groupby("subcorpus")[factor_columns].mean()

    for factor_column in factor_columns:
        for pole, ascending in (("pos", False), ("neg", True)):
            label = f"{factor_column}_{pole}"

            ranked_subcorpora = (
                means_df[factor_column]
                .sort_values(ascending=ascending)
                .index
                .tolist()
            )

            if not ranked_subcorpora:
                print(f"  No subcorpora found for {label}; skipping.")
                continue

            top_subcorpus = ranked_subcorpora[0]
            other_subcorpora = ranked_subcorpora[1:]

            print(
                f"→ {label}: selecting by subcorpus means "
                f"(ranked: {', '.join(ranked_subcorpora)})"
            )

            out_dir = output_dir / label
            out_dir.mkdir(parents=True, exist_ok=True)

            features = loading_features_lookup.get(label, [])
            sorted_df = scores_df.sort_values(by=factor_column, ascending=ascending)

            example_id = 1

            top_subcorpus_df = sorted_df[sorted_df["subcorpus"] == top_subcorpus]
            example_id = write_selected_examples_for_subcorpus(
                rows_df=top_subcorpus_df,
                factor_column=factor_column,
                quota=args.top_subcorpus_examples,
                label=label,
                out_dir=out_dir,
                start_example_id=example_id,
                corpus_dir=corpus_dir,
                features=features,
                missing_files=missing_files,
            )

            for other_subcorpus in other_subcorpora:
                other_subcorpus_df = sorted_df[sorted_df["subcorpus"] == other_subcorpus]
                example_id = write_selected_examples_for_subcorpus(
                    rows_df=other_subcorpus_df,
                    factor_column=factor_column,
                    quota=args.other_subcorpus_examples,
                    label=label,
                    out_dir=out_dir,
                    start_example_id=example_id,
                    corpus_dir=corpus_dir,
                    features=features,
                    missing_files=missing_files,
                )

            print(f"  ✓ Wrote {example_id - 1} examples for {label}\n")

    if missing_files:
        missing_path = output_dir / "missing_files.txt"
        missing_path.write_text("\n".join(sorted(missing_files)) + "\n", encoding="utf-8")
        print(f"⚠ Missing files written to {missing_path}")


if __name__ == "__main__":
    main()