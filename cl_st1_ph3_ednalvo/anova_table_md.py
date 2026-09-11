#!/usr/bin/env python3
"""
Generate a Markdown ANOVA summary table from Phase 3 SAS CSV outputs.

The programme reads per-factor ANOVA and R² CSV files from:

    sas/output_<project>/

Expected files include:

    anova_subcorpus_f1.csv
    r2_subcorpus_f1.csv
    anova_subcorpus_f2.csv
    r2_subcorpus_f2.csv
    ...

It writes:

    anova_table_md/anova_by_subcorpus.md
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PROJECT = Path.cwd().name
DEFAULT_OUTPUT_DIR = Path("anova_table_md")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate ANOVA Markdown table from Phase 3 SAS CSV outputs."
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
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory to save the Markdown table. Default: anova_table_md.",
    )

    return parser.parse_args()


def natural_sort_key(value: str) -> list[Any]:
    """Return a natural-sort key that treats digit runs as integers."""
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", value)
    ]


def resolve_sas_output_dir(project: str, sas_output_dir_arg: str | None) -> Path:
    """Resolve the SAS output directory."""
    if sas_output_dir_arg is None:
        return Path("sas") / f"output_{project}"
    return Path(sas_output_dir_arg)


def factor_from_filename(path: Path) -> str:
    """Extract factor label from a filename such as anova_subcorpus_f1.csv."""
    match = re.search(r"(f\d+)", path.stem)
    if not match:
        raise ValueError(f"Could not extract factor from filename: {path}")
    return match.group(1)


def find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Find a dataframe column by case-insensitive candidate names."""
    normalised = {str(column).strip().lower(): str(column) for column in df.columns}

    for candidate in candidates:
        key = candidate.strip().lower()
        if key in normalised:
            return normalised[key]

    return None


def extract_anova_stats(anova_file: Path) -> tuple[str, str]:
    """Extract F and p values from one SAS ANOVA CSV file."""
    df = pd.read_csv(anova_file)

    source_col = find_column(df, ["Source", "source"])
    f_col = find_column(df, ["F Value", "FValue", "F"])
    p_col = find_column(df, ["Pr > F", "ProbF", "p"])

    if source_col is not None:
        source_rows = df[df[source_col].astype(str).str.strip().str.lower() == "subcorpus"]
        if not source_rows.empty:
            row = source_rows.iloc[0]
        else:
            row = df.iloc[0]
    else:
        row = df.iloc[0]

    f_value = "N/A" if f_col is None else str(row[f_col]).strip()
    p_value = "N/A" if p_col is None else str(row[p_col]).strip().replace("&lt;", "<")

    return f_value, p_value


def extract_r2(r2_file: Path) -> str:
    """Extract R² percentage from one SAS fit-statistics CSV file."""
    if not r2_file.exists():
        return "N/A"

    df = pd.read_csv(r2_file)

    r2_col = find_column(df, ["R-Square", "RSquare", "R2", "R²"])
    if r2_col is None:
        return "N/A"

    r2 = float(df.iloc[0][r2_col])
    return f"{r2 * 100:.2f}"


def main() -> None:
    """Build the ANOVA-by-subcorpus Markdown table."""
    args = parse_args()

    sas_output_dir = resolve_sas_output_dir(args.project, args.sas_output_dir)
    output_dir = Path(args.output_dir)

    if not sas_output_dir.exists():
        raise FileNotFoundError(f"SAS output directory not found: {sas_output_dir}")

    anova_files = sorted(
        sas_output_dir.glob("anova_subcorpus_f*.csv"),
        key=lambda path: natural_sort_key(path.name),
    )

    if not anova_files:
        raise FileNotFoundError(
            f"No ANOVA CSV files found in {sas_output_dir} matching anova_subcorpus_f*.csv"
        )

    rows: list[dict[str, str]] = []

    for anova_file in anova_files:
        factor = factor_from_filename(anova_file)
        dim_num = factor.replace("f", "")
        r2_file = sas_output_dir / f"r2_subcorpus_{factor}.csv"

        f_value, p_value = extract_anova_stats(anova_file)
        r2_pct = extract_r2(r2_file)

        rows.append(
            {
                "Dimension": dim_num,
                "F": f_value,
                "p": p_value,
                "R2": r2_pct,
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "anova_by_subcorpus.md"

    md_lines = [
        "Table: ANOVA by Subcorpus",
        "",
        "| Dimension | F | p | R² % |",
        "|---|---:|---:|---:|",
    ]

    for row in rows:
        md_lines.append(
            f"| {row['Dimension']} | {row['F']} | {row['p']} | {row['R2']} |"
        )

    out_file.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"✓ Created {out_file}")


if __name__ == "__main__":
    main()