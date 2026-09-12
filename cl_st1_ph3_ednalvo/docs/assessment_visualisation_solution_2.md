# Assessment Visualisation Solution

> User:
> 
> Please refer to the attached thread. Can you guide me in the implementation in this Jupyter Notebook?

Yes. Your notebook is currently basically a blank working notebook with title/header cells, so the cleanest implementation is to build it in **sections**:

1. Load the human-assessed original score table.
2. Parse the AI-assessment Markdown files.
3. Standardise everything into one long-format scoring DataFrame.
4. Merge linguistic feature matrices.
5. Create comparison DataFrames.
6. Generate validation checks and visualisations.

Below is a notebook-ready implementation you can paste as successive cells.

---

## 1. Setup cell

```python
from pathlib import Path
import re

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

PROJECT_DIR = Path("/home/eyamrog/PycharmProjects/cl_st1_ednalvo/cl_st1_ph3_ednalvo")

ORIGINAL_SCORES_PATH = PROJECT_DIR / "corpus/00_fontes/composicoes_de_admissao_universitaria.tsv"
AI_ASSESSMENTS_DIR = PROJECT_DIR / "corpus/04_composicoes_avaliadas"
SAS_DIR = PROJECT_DIR / "sas"

SCORE_COLS = [
    "adequacao_ao_tema",
    "adequacao_a_coletanea",
    "adequacao_ao_tipo_de_texto",
    "adequacao_a_norma_padrao",
    "coesao",
    "coerencia",
]

TOTAL_COL = "pontuacao_total"

CANDIDATE_GROUP_ORDER = [
    "human_high",
    "human_low",
    "gemini_low_mirror",
    "gpt_low_mirror",
]
```


---

## 2. Load and standardise human-assessed original scores

```python
df_human_scores = pd.read_csv(ORIGINAL_SCORES_PATH, sep="\t")

df_human_scores["base_id"] = df_human_scores["inscricao"].astype(str)

df_human_scores["candidate_source"] = "human"
df_human_scores["candidate_band"] = df_human_scores["grupo"].map({
    "250_maiores_notas": "high",
    "250_menores_notas": "low",
})

df_human_scores["candidate_group"] = df_human_scores["candidate_band"].map({
    "high": "human_high",
    "low": "human_low",
})

df_human_scores["is_mirror"] = False
df_human_scores["mirror_model"] = pd.NA

df_human_scores["assessor_source"] = "human"
df_human_scores["assessor_model"] = pd.NA
df_human_scores["score_source_file"] = str(ORIGINAL_SCORES_PATH)

df_human_scores["composition_id"] = (
    df_human_scores["base_id"] + "_" + df_human_scores["candidate_group"]
)

df_human_scores = df_human_scores.rename(columns={
    "arquivo_original": "filename_original",
    "caminho_em_composicoes": "path",
})

for col in SCORE_COLS + [TOTAL_COL]:
    df_human_scores[col] = pd.to_numeric(df_human_scores[col], errors="coerce")

df_human_scores["score_sum_check"] = df_human_scores[SCORE_COLS].sum(axis=1)
df_human_scores["score_residual"] = (
    df_human_scores[TOTAL_COL] - df_human_scores["score_sum_check"]
)

df_human_scores.head()
```


---

## 3. Parse AI-assessment Markdown files

Your AI score outputs are stored as Markdown files with a scoring table. This parser extracts the six criterion scores plus total score.

```python
CRITERION_PATTERNS = {
    "adequacao_ao_tema": r"Adequa[cç][aã]o ao Tema",
    "adequacao_a_coletanea": r"Adequa[cç][aã]o [àa] Colet[âa]nea",
    "adequacao_ao_tipo_de_texto": r"Adequa[cç][aã]o ao tipo de texto",
    "adequacao_a_norma_padrao": r"Adequa[cç][aã]o [àa] norma padr[aã]o",
    "coesao": r"Coes[aã]o",
    "coerencia": r"Coer[êe]ncia",
    "pontuacao_total": r"Pontua[cç][aã]o Total",
}


def parse_ptbr_number(value: str) -> float:
    value = value.strip()
    value = value.replace("**", "")
    value = value.replace(",", ".")
    value = re.sub(r"[^0-9.\-]", "", value)
    return float(value) if value else np.nan


def extract_score_from_markdown(text: str, criterion_regex: str) -> float:
    pattern = rf"\|\s*[^|]*{criterion_regex}[^|]*\|\s*([^|]+?)\s*\|"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return np.nan
    return parse_ptbr_number(match.group(1))


def parse_ai_assessment_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    
    base_id_match = re.search(r"(\d+)_avaliacao_", path.name)
    base_id = base_id_match.group(1) if base_id_match else pd.NA
    
    row = {
        "base_id": str(base_id),
        "ai_assessment_filename": path.name,
        "ai_assessment_path": str(path),
        "score_source_file": str(path),
    }
    
    for col, pattern in CRITERION_PATTERNS.items():
        row[col] = extract_score_from_markdown(text, pattern)
    
    return row
```


Quickly test on one file:

```python
example_file = next((AI_ASSESSMENTS_DIR / "maiores_notas").glob("*_avaliacao_*.md"))
parse_ai_assessment_file(example_file)
```


---

## 4. Load all AI-assessed scores

This maps your folder names to analysis labels.

```python
AI_GROUP_MAP = {
    "maiores_notas": {
        "candidate_group": "human_high",
        "candidate_source": "human",
        "candidate_band": "high",
        "is_mirror": False,
        "mirror_model": pd.NA,
    },
    "menores_notas": {
        "candidate_group": "human_low",
        "candidate_source": "human",
        "candidate_band": "low",
        "is_mirror": False,
        "mirror_model": pd.NA,
    },
    "menores_notas_gemini": {
        "candidate_group": "gemini_low_mirror",
        "candidate_source": "gemini",
        "candidate_band": "low_mirror",
        "is_mirror": True,
        "mirror_model": "gemini",
    },
    "menores_notas_gpt": {
        "candidate_group": "gpt_low_mirror",
        "candidate_source": "gpt",
        "candidate_band": "low_mirror",
        "is_mirror": True,
        "mirror_model": "gpt",
    },
}


def load_ai_assessment_folder(folder_name: str, assessor_model: str = "gpt-5.6-sol") -> pd.DataFrame:
    folder = AI_ASSESSMENTS_DIR / folder_name
    files = sorted(folder.glob("*_avaliacao_*.md"))
    
    rows = [parse_ai_assessment_file(path) for path in files]
    df = pd.DataFrame(rows)
    
    meta = AI_GROUP_MAP[folder_name]
    for key, value in meta.items():
        df[key] = value
    
    df["assessor_source"] = "gpt_ai"
    df["assessor_model"] = assessor_model
    
    df["composition_id"] = df["base_id"] + "_" + df["candidate_group"]
    df["filename"] = df["base_id"] + ".txt"
    
    for col in SCORE_COLS + [TOTAL_COL]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    
    df["score_sum_check"] = df[SCORE_COLS].sum(axis=1)
    df["score_residual"] = df[TOTAL_COL] - df["score_sum_check"]
    
    return df


df_ai_scores = pd.concat(
    [
        load_ai_assessment_folder("maiores_notas"),
        load_ai_assessment_folder("menores_notas"),
        load_ai_assessment_folder("menores_notas_gemini"),
        load_ai_assessment_folder("menores_notas_gpt"),
    ],
    ignore_index=True,
)

df_ai_scores.head()
```


---

## 5. Build the canonical long-format score table

This is the most important table.

```python
COMMON_SCORE_COLS = [
    "composition_id",
    "base_id",
    "candidate_source",
    "candidate_group",
    "candidate_band",
    "is_mirror",
    "mirror_model",
    "assessor_source",
    "assessor_model",
    "path",
    "filename",
    "filename_original",
    "ai_assessment_filename",
    "ai_assessment_path",
    "score_source_file",
    *SCORE_COLS,
    TOTAL_COL,
    "score_sum_check",
    "score_residual",
]

for col in COMMON_SCORE_COLS:
    if col not in df_human_scores.columns:
        df_human_scores[col] = pd.NA
    if col not in df_ai_scores.columns:
        df_ai_scores[col] = pd.NA

df_scores_long = pd.concat(
    [
        df_human_scores[COMMON_SCORE_COLS],
        df_ai_scores[COMMON_SCORE_COLS],
    ],
    ignore_index=True,
)

for col in SCORE_COLS + [TOTAL_COL, "score_sum_check", "score_residual"]:
    df_scores_long[col] = pd.to_numeric(df_scores_long[col], errors="coerce")

df_scores_long["candidate_group"] = pd.Categorical(
    df_scores_long["candidate_group"],
    categories=CANDIDATE_GROUP_ORDER,
    ordered=True,
)

df_scores_long.head()
```


Conceptually:

- `df_scores_long` has **one row per composition × assessor**.
- The original human essays should have human and AI rows.
- The LLM mirrored essays should have AI rows only.

---

## 6. Validation checks

Run this before plotting.

```python
print("Rows by candidate group and assessor:")
display(
    df_scores_long
    .groupby(["candidate_group", "assessor_source"], observed=False)
    .size()
    .reset_index(name="n")
)

print("Unique compositions by candidate group:")
display(
    df_scores_long[["composition_id", "candidate_group"]]
    .drop_duplicates()
    .groupby("candidate_group", observed=False)
    .size()
    .reset_index(name="n_compositions")
)

print("Score residual summary:")
display(df_scores_long["score_residual"].describe())

print("Missing AI score fields:")
display(df_ai_scores[SCORE_COLS + [TOTAL_COL]].isna().sum())

print("Duplicate assessment rows:")
duplicate_count = df_scores_long.duplicated(
    subset=["composition_id", "assessor_source", "assessor_model"]
).sum()
display(duplicate_count)
```


Expected conceptual pattern:

```plain text
human_high          human      250
human_high          gpt_ai     250
human_low           human      250
human_low           gpt_ai     250
gemini_low_mirror   gpt_ai     250
gpt_low_mirror      gpt_ai     250
```


If the counts differ, the missing files or parse failures are what we debug first.

---

## 7. Merge linguistic feature matrices

This gives you a fuller `df_main` with scores plus `wcount`, `v001`, `v002`, etc.

```python
FEATURE_FILES = {
    "human_high": SAS_DIR / "maiores_notas_counts.tsv",
    "human_low": SAS_DIR / "menores_notas_counts.tsv",
    "gemini_low_mirror": SAS_DIR / "menores_notas_gemini_counts.tsv",
    "gpt_low_mirror": SAS_DIR / "menores_notas_gpt_counts.tsv",
}

feature_frames = []

for candidate_group, path in FEATURE_FILES.items():
    temp = pd.read_csv(path, sep="\t")
    temp["candidate_group"] = candidate_group
    temp["base_id"] = temp["filename"].str.extract(r"(\d+)")[0].astype(str)
    temp["composition_id"] = temp["base_id"] + "_" + temp["candidate_group"]
    feature_frames.append(temp)

df_features = pd.concat(feature_frames, ignore_index=True)

df_main = df_scores_long.merge(
    df_features,
    on=["composition_id", "base_id", "candidate_group"],
    how="left",
    suffixes=("", "_feature"),
)

df_main.head()
```


---

## 8. Derived DataFrame: human vs AI assessors

Use this only for **human-authored compositions**, because only these have both human and AI scores.

```python
df_assessor_compare = (
    df_scores_long
    .query("candidate_source == 'human'")
    .pivot_table(
        index=["composition_id", "base_id", "candidate_band", "candidate_group"],
        columns="assessor_source",
        values=[*SCORE_COLS, TOTAL_COL],
        aggfunc="first",
    )
)

df_assessor_compare.columns = [
    f"{score}_{assessor}"
    for score, assessor in df_assessor_compare.columns
]

df_assessor_compare = df_assessor_compare.reset_index()

df_assessor_compare["total_diff_ai_minus_human"] = (
    df_assessor_compare["pontuacao_total_gpt_ai"]
    - df_assessor_compare["pontuacao_total_human"]
)

df_assessor_compare["total_abs_diff"] = (
    df_assessor_compare["total_diff_ai_minus_human"].abs()
)

df_assessor_compare.head()
```


---

## 9. Derived DataFrame: human low originals vs LLM rewrites

Use this for the candidate comparison, under the **same AI assessor**.

```python
df_candidate_compare = (
    df_scores_long
    .query("assessor_source == 'gpt_ai'")
    .pivot_table(
        index="base_id",
        columns="candidate_group",
        values=[*SCORE_COLS, TOTAL_COL],
        aggfunc="first",
    )
)

df_candidate_compare.columns = [
    f"{score}_{group}"
    for score, group in df_candidate_compare.columns
]

df_candidate_compare = df_candidate_compare.reset_index()

df_candidate_compare["gain_gemini_vs_human_low"] = (
    df_candidate_compare["pontuacao_total_gemini_low_mirror"]
    - df_candidate_compare["pontuacao_total_human_low"]
)

df_candidate_compare["gain_gpt_vs_human_low"] = (
    df_candidate_compare["pontuacao_total_gpt_low_mirror"]
    - df_candidate_compare["pontuacao_total_human_low"]
)

df_candidate_compare["diff_gpt_minus_gemini"] = (
    df_candidate_compare["pontuacao_total_gpt_low_mirror"]
    - df_candidate_compare["pontuacao_total_gemini_low_mirror"]
)

df_candidate_compare.head()
```


---

## 10. First visualisations

### AI-assessed total scores by candidate group

```python
plt.figure(figsize=(10, 5))

plot_data = df_scores_long.query("assessor_source == 'gpt_ai'")

sns.boxplot(
    data=plot_data,
    x="candidate_group",
    y="pontuacao_total",
    order=CANDIDATE_GROUP_ORDER,
)

sns.stripplot(
    data=plot_data,
    x="candidate_group",
    y="pontuacao_total",
    order=CANDIDATE_GROUP_ORDER,
    color="black",
    alpha=0.25,
    size=2,
)

plt.xticks(rotation=30, ha="right")
plt.title("AI-assessed total scores by candidate group")
plt.xlabel("Candidate group")
plt.ylabel("Total score")
plt.tight_layout()
plt.show()
```


### Human vs AI total score

```python
plt.figure(figsize=(6, 6))

sns.scatterplot(
    data=df_assessor_compare,
    x="pontuacao_total_human",
    y="pontuacao_total_gpt_ai",
    hue="candidate_band",
    alpha=0.7,
)

max_score = max(
    df_assessor_compare["pontuacao_total_human"].max(),
    df_assessor_compare["pontuacao_total_gpt_ai"].max(),
)

plt.plot([0, max_score], [0, max_score], linestyle="--", color="gray")

plt.title("Human vs AI total score on human-authored compositions")
plt.xlabel("Human assessor total")
plt.ylabel("AI assessor total")
plt.tight_layout()
plt.show()
```


### Rewrite score gains

```python
gain_long = df_candidate_compare.melt(
    id_vars="base_id",
    value_vars=[
        "gain_gemini_vs_human_low",
        "gain_gpt_vs_human_low",
    ],
    var_name="model",
    value_name="score_gain",
)

gain_long["model"] = gain_long["model"].map({
    "gain_gemini_vs_human_low": "Gemini rewrite",
    "gain_gpt_vs_human_low": "GPT rewrite",
})

plt.figure(figsize=(7, 5))

sns.boxplot(
    data=gain_long,
    x="model",
    y="score_gain",
)

sns.stripplot(
    data=gain_long,
    x="model",
    y="score_gain",
    color="black",
    alpha=0.25,
    size=2,
)

plt.axhline(0, color="gray", linestyle="--")
plt.title("AI-assessed score gains from rewriting low-mark compositions")
plt.xlabel("")
plt.ylabel("Total score gain over original low human text")
plt.tight_layout()
plt.show()
```


---

## 11. Save persistent analysis tables

```python
OUTPUT_DIR = PROJECT_DIR / "analysis_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

df_scores_long.to_csv(OUTPUT_DIR / "df_scores_long.csv", index=False)
df_assessor_compare.to_csv(OUTPUT_DIR / "df_assessor_compare.csv", index=False)
df_candidate_compare.to_csv(OUTPUT_DIR / "df_candidate_compare.csv", index=False)
df_main.to_csv(OUTPUT_DIR / "df_main_scores_features.csv", index=False)

print(f"Saved outputs to: {OUTPUT_DIR}")
```


---

## Suggested notebook structure

I would organise the notebook with these markdown headings:

```markdown
# Evaluation of Compositions

## 1. Setup

## 2. Human-assessed original scores

## 3. AI-assessed score parsing

## 4. Canonical long-format scoring table

## 5. Validation checks

## 6. Linguistic feature merge

## 7. Human vs AI assessor comparison

## 8. Human low originals vs LLM rewrites

## 9. Visualisations

## 10. Export analysis tables
```


The main thing is to keep the conceptual distinction clear:

- **Assessor comparison:** same human-authored composition, different assessor.
- **Candidate/source comparison:** same AI assessor, different candidate source.