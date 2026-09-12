# Assessment Visualisation Solution

> User:
>
> I've got an original dataset of university entrance compositions (attached) in which human assessors graded each composition. The dataset is split into 250 high-mark and 250 low-mark compositions. The low-mark compositions were rewritten by Gemini and GPT LLMs acting as mirrored candidates. So, the low-mark compositions account for 250 + 250 + 250 mirrored compositions. Therefore, the total of compositions is 250 high-mark human-authored plus the 750 low-mark compositions = 1,000 compositions.
>
> All of them were graded by AI assessors (GPT).
>
>Each grade is composed by 6 grading elements whose sum results in a total mark:
>
> ```
> - adequacao_ao_tema
> - adequacao_a_coletanea
> - adequacao_ao_tipo_de_texto
> - adequacao_a_norma_padrao
> - coesao
> - coerencia
> - pontuacao_total
> ```
> 
>
> I am trying to arrange the data into a main DataFrame from which I could extract insightful visualisations, especially how human and AI assessors compare and how human and AI candidates compare.
>
> Could you help me devise a solution for this?

## Goal

You want one **analysis-ready main DataFrame** that can represent:

1. **Who authored the composition**
   - Human high-mark candidate
   - Human low-mark candidate
   - Gemini mirrored candidate
   - GPT mirrored candidate

2. **Who assessed it**
   - Human assessor
   - AI assessor, e.g. GPT

3. **What was assessed**
   - The same six rubric elements plus total score

4. **How compositions are linked**
   - Especially: each rewritten low-mark composition should remain linked to its original low-mark human composition.

The most flexible solution is to build the data in **long/tidy format**, then derive wide comparison tables only when needed.

---

## 1. Recommended analytical unit

Use this as the core unit:

> **one row = one composition × one assessor source**

So, if a composition has both a human score and an AI score, it appears twice:

| composition_id | base_id | candidate_source | candidate_band | assessor_source | adequacao_ao_tema | ... | pontuacao_total |
|---|---|---|---|---|---:|---|---:|
| `36237_human_high` | `36237` | `human` | `high` | `human` | 4.5 | ... | 29.5 |
| `36237_human_high` | `36237` | `human` | `high` | `gpt_ai` | 4.0 | ... | 28.0 |
| `34356_human_low` | `34356` | `human` | `low` | `human` | 0.0 | ... | 0.0 |
| `34356_human_low` | `34356` | `human` | `low` | `gpt_ai` | 1.0 | ... | 5.5 |
| `34356_gemini_low_mirror` | `34356` | `gemini` | `low_mirror` | `gpt_ai` | 3.5 | ... | 21.0 |
| `34356_gpt_low_mirror` | `34356` | `gpt` | `low_mirror` | `gpt_ai` | 4.0 | ... | 22.0 |

The key is the distinction between:

- `composition_id`: unique text actually assessed.
- `base_id`: original candidate/composition that this text derives from.
- `candidate_source`: who authored the text.
- `assessor_source`: who graded it.

This lets you ask both:

- **Human vs AI assessors**: compare scores for the same human-authored compositions.
- **Human vs AI candidates**: compare human low-mark originals to their Gemini/GPT rewrites under the same AI assessor.

---

## 2. Core metadata columns

I recommend these columns in the main DataFrame:

| Column | Meaning |
|---|---|
| `composition_id` | Unique ID for each actual composition text |
| `base_id` | Original `inscricao` / source ID; shared by low original + mirrored rewrites |
| `filename` | File name, when available |
| `path` | Path to text file |
| `candidate_source` | `human`, `gemini`, `gpt` |
| `candidate_group` | `human_high`, `human_low`, `gemini_low_mirror`, `gpt_low_mirror` |
| `candidate_band` | `high`, `low`, `low_mirror` |
| `is_mirror` | `True` for LLM rewrites |
| `mirror_model` | `gemini`, `gpt`, or `None` |
| `assessor_source` | `human`, `gpt_ai` |
| `assessor_model` | e.g. `gpt-5.5`, if known |
| `score_source_file` | Optional provenance of the scoring file |
| `adequacao_ao_tema` | Score component |
| `adequacao_a_coletanea` | Score component |
| `adequacao_ao_tipo_de_texto` | Score component |
| `adequacao_a_norma_padrao` | Score component |
| `coesao` | Score component |
| `coerencia` | Score component |
| `pontuacao_total` | Total score |
| `score_sum_check` | Sum of six components |
| `score_residual` | `pontuacao_total - score_sum_check` |
| `wcount` | Optional word count from feature files |
| linguistic features | Optional `v001`, `v002`, ..., if you merge TMDA features |

This structure also keeps the door open to multiple AI assessors later.

---

## 3. Suggested workflow

### Step A — Load original human-assessed scores

Your human-assessed original dataset already contains the six rubric elements plus total score for:

- 250 high-mark human-authored compositions
- 250 low-mark human-authored compositions

Load it as human-assessor data and standardise the labels.

```python
import pandas as pd
from pathlib import Path

SCORE_COLS = [
    "adequacao_ao_tema",
    "adequacao_a_coletanea",
    "adequacao_ao_tipo_de_texto",
    "adequacao_a_norma_padrao",
    "coesao",
    "coerencia",
]

TOTAL_COL = "pontuacao_total"

original_path = Path("corpus/00_fontes/composicoes_de_admissao_universitaria.tsv")

df_human_scores = pd.read_csv(original_path, sep="\t")

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

df_human_scores["composition_id"] = (
    df_human_scores["base_id"]
    + "_"
    + df_human_scores["candidate_group"]
)

df_human_scores = df_human_scores.rename(columns={
    "arquivo_original": "filename_original",
    "caminho_em_composicoes": "path",
})

df_human_scores["score_sum_check"] = df_human_scores[SCORE_COLS].sum(axis=1)
df_human_scores["score_residual"] = (
    df_human_scores[TOTAL_COL] - df_human_scores["score_sum_check"]
)
```


---

### Step B — Load AI-assessed scores

Assuming your AI-assessed compositions are stored as one or more structured files, the important thing is to standardise them into the same schema.

You may have AI score outputs for:

- high human compositions
- low human compositions
- Gemini rewrites
- GPT rewrites

Your loader should return the same key columns:

```python
def standardise_ai_scores(
    df: pd.DataFrame,
    candidate_group: str,
    assessor_model: str = "gpt",
) -> pd.DataFrame:
    df = df.copy()

    if "inscricao" in df.columns:
        df["base_id"] = df["inscricao"].astype(str)
    elif "base_id" in df.columns:
        df["base_id"] = df["base_id"].astype(str)
    elif "filename" in df.columns:
        df["base_id"] = df["filename"].str.extract(r"(\d+)")[0]
    else:
        raise ValueError("Cannot infer base_id. Provide inscricao, base_id, or filename.")

    candidate_map = {
        "human_high": {
            "candidate_source": "human",
            "candidate_band": "high",
            "is_mirror": False,
            "mirror_model": pd.NA,
        },
        "human_low": {
            "candidate_source": "human",
            "candidate_band": "low",
            "is_mirror": False,
            "mirror_model": pd.NA,
        },
        "gemini_low_mirror": {
            "candidate_source": "gemini",
            "candidate_band": "low_mirror",
            "is_mirror": True,
            "mirror_model": "gemini",
        },
        "gpt_low_mirror": {
            "candidate_source": "gpt",
            "candidate_band": "low_mirror",
            "is_mirror": True,
            "mirror_model": "gpt",
        },
    }

    meta = candidate_map[candidate_group]

    for key, value in meta.items():
        df[key] = value

    df["candidate_group"] = candidate_group
    df["assessor_source"] = "gpt_ai"
    df["assessor_model"] = assessor_model

    df["composition_id"] = df["base_id"] + "_" + candidate_group

    if "path" not in df.columns and "caminho_em_composicoes" in df.columns:
        df = df.rename(columns={"caminho_em_composicoes": "path"})

    df["score_sum_check"] = df[SCORE_COLS].sum(axis=1)
    df["score_residual"] = df[TOTAL_COL] - df["score_sum_check"]

    return df
```


Then you can use it like this, adapting paths and file names to your actual AI assessment outputs:

```python
# Examples only: adjust these paths to match your actual AI scoring files.

df_ai_human_high_raw = pd.read_json(
    "corpus/04_composicoes_avaliadas/maiores_notas/scores.ndjson",
    lines=True,
)

df_ai_human_low_raw = pd.read_json(
    "corpus/04_composicoes_avaliadas/menores_notas/scores.ndjson",
    lines=True,
)

df_ai_gemini_raw = pd.read_json(
    "corpus/04_composicoes_avaliadas/menores_notas_gemini/scores.ndjson",
    lines=True,
)

df_ai_gpt_raw = pd.read_json(
    "corpus/04_composicoes_avaliadas/menores_notas_gpt/scores.ndjson",
    lines=True,
)

df_ai_scores = pd.concat(
    [
        standardise_ai_scores(df_ai_human_high_raw, "human_high"),
        standardise_ai_scores(df_ai_human_low_raw, "human_low"),
        standardise_ai_scores(df_ai_gemini_raw, "gemini_low_mirror"),
        standardise_ai_scores(df_ai_gpt_raw, "gpt_low_mirror"),
    ],
    ignore_index=True,
)
```


If the AI assessment outputs are one JSON file per composition rather than a single table, you can read them folder-by-folder and concatenate them first.

---

### Step C — Build the main long DataFrame

```python
common_cols = [
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
    *SCORE_COLS,
    TOTAL_COL,
    "score_sum_check",
    "score_residual",
]

for col in common_cols:
    if col not in df_human_scores.columns:
        df_human_scores[col] = pd.NA
    if col not in df_ai_scores.columns:
        df_ai_scores[col] = pd.NA

df_scores_long = pd.concat(
    [
        df_human_scores[common_cols],
        df_ai_scores[common_cols],
    ],
    ignore_index=True,
)

df_scores_long["pontuacao_total"] = pd.to_numeric(
    df_scores_long["pontuacao_total"],
    errors="coerce",
)
```


You can now verify expected counts:

```python
df_scores_long.groupby(
    ["candidate_group", "assessor_source"]
).size().reset_index(name="n")
```


Expected conceptual result, if all assessments are present:

| candidate_group | human assessor | AI assessor |
|---|---:|---:|
| `human_high` | 250 | 250 |
| `human_low` | 250 | 250 |
| `gemini_low_mirror` | 0 | 250 |
| `gpt_low_mirror` | 0 | 250 |

So the long table would have:

- 500 human-assessor rows
- 1,000 AI-assessor rows
- 1,500 score rows total

Even though there are 1,000 actual compositions.

That is good: the long table represents **assessments**, not just texts.

---

## 4. Optional: merge linguistic feature counts

If you want to connect scoring with linguistic profiles, merge the feature matrices.

```python
feature_files = [
    "maiores_notas_counts.tsv",
    "menores_notas_counts.tsv",
    "menores_notas_gemini_counts.tsv",
    "menores_notas_gpt_counts.tsv",
]

df_features = pd.concat(
    [pd.read_csv(path, sep="\t") for path in feature_files],
    ignore_index=True,
)

df_features["base_id"] = df_features["filename"].str.extract(r"(\d+)")[0]

df_features["candidate_group"] = df_features["subcorpus"].map({
    "maiores_notas": "human_high",
    "menores_notas": "human_low",
    "menores_notas_gemini": "gemini_low_mirror",
    "menores_notas_gpt": "gpt_low_mirror",
})

df_features["composition_id"] = (
    df_features["base_id"] + "_" + df_features["candidate_group"]
)

df_main = df_scores_long.merge(
    df_features,
    on=["composition_id", "base_id", "candidate_group"],
    how="left",
    suffixes=("", "_feature"),
)
```


For most visualisations, you may not need all `v001`–`v230` columns in the main scoring table. But merging them into `df_main` lets you examine relationships such as:

- AI score vs word count
- AI score vs linguistic dimensions
- Gemini/GPT score gain vs linguistic features
- human-assessor score vs TMDA factor scores, if you later merge factor scores

---

## 5. Derived comparison DataFrames

The long table is the main canonical dataset, but some analyses are easier after pivoting.

---

### A. Human assessor vs AI assessor on human-authored compositions

Use only human-authored compositions that have both human and AI assessments.

```python
df_assessor_compare = (
    df_scores_long
    .query("candidate_source == 'human'")
    .pivot_table(
        index=["composition_id", "base_id", "candidate_band"],
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
```


Useful questions:

- Does GPT grade systematically higher or lower than humans?
- Is the bias different for high vs low human essays?
- Which rubric components differ the most?

---

### B. Human low originals vs Gemini/GPT mirrored candidates

This comparison should be done using the **same assessor**, preferably the AI assessor, because the mirrored texts do not have human grades.

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
```


Useful questions:

- How much did Gemini improve low-mark essays?
- How much did GPT improve them?
- Which model produces higher-scoring mirrored candidates?
- Which grading criteria benefit most from rewriting?

---

## 6. Recommended visualisations

### 6.1 Score distributions by candidate type

Good first overview.

```python
import seaborn as sns
import matplotlib.pyplot as plt

plt.figure(figsize=(10, 5))

sns.boxplot(
    data=df_scores_long.query("assessor_source == 'gpt_ai'"),
    x="candidate_group",
    y="pontuacao_total",
    order=[
        "human_high",
        "human_low",
        "gemini_low_mirror",
        "gpt_low_mirror",
    ],
)

sns.stripplot(
    data=df_scores_long.query("assessor_source == 'gpt_ai'"),
    x="candidate_group",
    y="pontuacao_total",
    color="black",
    alpha=0.25,
    size=2,
    order=[
        "human_high",
        "human_low",
        "gemini_low_mirror",
        "gpt_low_mirror",
    ],
)

plt.xticks(rotation=30, ha="right")
plt.title("AI-assessed total scores by candidate group")
plt.xlabel("Candidate group")
plt.ylabel("Total score")
plt.tight_layout()
plt.show()
```


This directly addresses **human vs AI candidates** under the same assessor.

---

### 6.2 Human vs AI assessor scatterplot

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


This answers:

> Do AI scores align with human scores?

Points above the line mean GPT graded higher than humans; points below mean lower.

---

### 6.3 Bland–Altman plot for human vs AI assessor

This is often better than a correlation plot for assessor comparison.

```python
df_assessor_compare["total_mean_human_ai"] = (
    df_assessor_compare["pontuacao_total_human"]
    + df_assessor_compare["pontuacao_total_gpt_ai"]
) / 2

plt.figure(figsize=(8, 5))

sns.scatterplot(
    data=df_assessor_compare,
    x="total_mean_human_ai",
    y="total_diff_ai_minus_human",
    hue="candidate_band",
    alpha=0.7,
)

plt.axhline(0, color="gray", linestyle="--")

plt.title("AI minus human score by average score")
plt.xlabel("Mean of human and AI total scores")
plt.ylabel("AI total - human total")
plt.tight_layout()
plt.show()
```


This shows whether AI disagreement is larger for low-scoring or high-scoring essays.

---

### 6.4 Rubric-element differences between human and AI assessors

```python
component_diffs = []

for col in SCORE_COLS:
    temp = df_assessor_compare[
        ["composition_id", "base_id", "candidate_band"]
    ].copy()

    temp["criterion"] = col
    temp["diff_ai_minus_human"] = (
        df_assessor_compare[f"{col}_gpt_ai"]
        - df_assessor_compare[f"{col}_human"]
    )

    component_diffs.append(temp)

df_component_diffs = pd.concat(component_diffs, ignore_index=True)

plt.figure(figsize=(10, 5))

sns.boxplot(
    data=df_component_diffs,
    x="criterion",
    y="diff_ai_minus_human",
    hue="candidate_band",
)

plt.axhline(0, color="gray", linestyle="--")
plt.xticks(rotation=45, ha="right")
plt.title("AI minus human score by rubric criterion")
plt.xlabel("Criterion")
plt.ylabel("AI score - human score")
plt.tight_layout()
plt.show()
```


This tells you whether GPT is harsher or more generous on:

- theme adequacy
- source-material adequacy
- text type
- standard language
- cohesion
- coherence

---

### 6.5 Mirrored-candidate score gains

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


This is likely one of your central visualisations.

---

### 6.6 Paired slope plot: original low vs Gemini/GPT rewrites

Because each mirrored text is linked to one original low-mark composition, this is a paired design.

```python
paired_total = df_scores_long.query(
    "assessor_source == 'gpt_ai' and candidate_group in "
    "['human_low', 'gemini_low_mirror', 'gpt_low_mirror']"
)[
    ["base_id", "candidate_group", "pontuacao_total"]
]

plt.figure(figsize=(9, 6))

sns.lineplot(
    data=paired_total,
    x="candidate_group",
    y="pontuacao_total",
    units="base_id",
    estimator=None,
    alpha=0.15,
    color="gray",
)

sns.pointplot(
    data=paired_total,
    x="candidate_group",
    y="pontuacao_total",
    errorbar=("ci", 95),
    color="red",
)

plt.xticks(rotation=30, ha="right")
plt.title("Paired AI-assessed score changes from low originals to rewrites")
plt.xlabel("Candidate group")
plt.ylabel("Total score")
plt.tight_layout()
plt.show()
```


This shows whether the rewrite uplift is general or driven by a few cases.

---

### 6.7 Rubric profile by candidate group

```python
df_rubric_long = df_scores_long.query("assessor_source == 'gpt_ai'").melt(
    id_vars=[
        "composition_id",
        "base_id",
        "candidate_group",
        "candidate_source",
    ],
    value_vars=SCORE_COLS,
    var_name="criterion",
    value_name="score",
)

plt.figure(figsize=(11, 5))

sns.barplot(
    data=df_rubric_long,
    x="criterion",
    y="score",
    hue="candidate_group",
    errorbar=("ci", 95),
    hue_order=[
        "human_high",
        "human_low",
        "gemini_low_mirror",
        "gpt_low_mirror",
    ],
)

plt.xticks(rotation=45, ha="right")
plt.title("AI-assessed rubric profile by candidate group")
plt.xlabel("Criterion")
plt.ylabel("Mean score")
plt.tight_layout()
plt.show()
```


This helps answer:

> Which criteria do LLM rewrites improve most?

For example, LLM rewrites may improve `coesao`, `coerencia`, and `adequacao_a_norma_padrao` more than `adequacao_a_coletanea`.

---

## 7. Statistical summaries worth extracting

### Assessor agreement

For human-authored compositions:

```python
from scipy.stats import pearsonr, spearmanr

pearson_total = pearsonr(
    df_assessor_compare["pontuacao_total_human"],
    df_assessor_compare["pontuacao_total_gpt_ai"],
)

spearman_total = spearmanr(
    df_assessor_compare["pontuacao_total_human"],
    df_assessor_compare["pontuacao_total_gpt_ai"],
)

mean_bias = df_assessor_compare["total_diff_ai_minus_human"].mean()
mae = df_assessor_compare["total_abs_diff"].mean()

pearson_total, spearman_total, mean_bias, mae
```


Report:

- Pearson correlation
- Spearman rank correlation
- mean AI-human difference
- mean absolute difference

---

### Candidate-source comparison under AI assessor

```python
summary_candidate_ai = (
    df_scores_long
    .query("assessor_source == 'gpt_ai'")
    .groupby("candidate_group")[TOTAL_COL]
    .agg(["count", "mean", "std", "median", "min", "max"])
    .reset_index()
)

summary_candidate_ai
```


---

### Rewrite gains

```python
rewrite_gain_summary = gain_long.groupby("model")["score_gain"].agg(
    ["count", "mean", "std", "median", "min", "max"]
)

rewrite_gain_summary
```


---

## 8. Important design distinction

There are two different comparisons, and you should avoid mixing them:

### Comparison 1 — Assessors

Use the **same compositions**, different assessors.

Example:

```
human-authored essay X:
    human score vs GPT score
```


This measures **assessment alignment or bias**.

---

### Comparison 2 — Candidates/authors

Use the **same assessor**, different candidate sources.

Example:

```
AI assessor grades:
    low human original vs Gemini rewrite vs GPT rewrite
```


This measures **candidate/source effect**, not assessor effect.

This distinction should be reflected in your plots and tables.

---

## 9. Recommended final DataFrame set

I would keep three persistent tables:

### `df_scores_long`

Canonical scoring table.

- One row per composition-assessment event.
- Best for plotting, grouping, modelling.

### `df_assessor_compare`

Human vs AI assessor comparison.

- One row per human-authored composition.
- Best for agreement, bias, residual plots.

### `df_candidate_compare`

Human low originals vs LLM mirrored rewrites.

- One row per original low-mark `base_id`.
- Best for paired rewrite-gain analysis.

Optionally:

### `df_main`

Long scoring table merged with linguistic features.

- Best for connecting score differences to linguistic variables or factor scores.

---

## 10. Minimal validation checks

Run these before visualisation:

```python
# 1. Check total score consistency
df_scores_long["score_residual"].describe()

# 2. Check row counts
df_scores_long.groupby(["candidate_group", "assessor_source"]).size()

# 3. Check that every mirrored composition has a base_id
df_scores_long.query("is_mirror == True")["base_id"].isna().sum()

# 4. Check candidate composition counts
df_scores_long[["composition_id", "candidate_group"]].drop_duplicates() \
    .groupby("candidate_group").size()

# 5. Check duplicate assessments
df_scores_long.duplicated(
    subset=["composition_id", "assessor_source", "assessor_model"]
).sum()
```


If everything is complete, you should see:

```plain text
human_high:          250 compositions
human_low:           250 compositions
gemini_low_mirror:   250 compositions
gpt_low_mirror:      250 compositions
```


and AI-assessed score rows for all 1,000 compositions.

---

## Bottom line

Use a **long-format main DataFrame** with explicit columns for:

- `candidate_source`
- `candidate_group`
- `candidate_band`
- `assessor_source`
- `composition_id`
- `base_id`

Then derive:

1. `df_assessor_compare` for **human vs AI grading**.
2. `df_candidate_compare` for **human vs AI-generated candidates**.
3. optional `df_main` merged with linguistic features for deeper explanatory analysis.

This gives you a clean foundation for boxplots, paired rewrite-gain plots, agreement plots, rubric profiles, and later statistical modelling.