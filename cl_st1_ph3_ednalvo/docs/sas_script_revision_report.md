# Full Report on the SAS Script Revision

## 1. Overall assessment

The SAS script is now in a **methodologically coherent and operationally verified state**. The final version runs without errors and implements a conservative Traditional Multi-Dimensional Analysis (TMDA) workflow for comparing human-written and LLM-generated Brazilian Portuguese entrance-exam essays.

The current workflow is:

1. Import the normalised DFM TSV files.
2. Combine all four subcorpora.
3. Exclude metadata and aggregate variables from factor extraction.
4. Detect and remove zero-variance variables before factor analysis.
5. Run unrotated factor analysis.
6. Remove variables below the communality cutoff.
7. Run final promax-rotated factor analysis.
8. Extract the rotated factor pattern using `_TYPE_="PATTERN"`.
9. Generate loadings tables and interpretation tables.
10. Score all compositions using the same feature set used in the final factor model.
11. Identify factor-score outliers for diagnostic inspection.
12. Keep all outliers in the final score and statistical-analysis datasets.
13. Run ANOVAs and boxplots by `subcorpus`.
14. Zip output files.

Given the intended downstream workflow — ranking the strongest compositions per factor pole using `&project._scores_only.csv` — keeping the outlier bypass active is justified and methodologically defensible.

---

## 2. Main methodological decisions now implemented

### 2.1 Summary variables are excluded from factor extraction

The script excludes the aggregate variables:
```text
v900-v919
```
from factor extraction.

This is methodologically appropriate because these variables are derived from lower-level variables and, if included together with their components, could introduce artificial covariance and overweight broad linguistic domains.

This decision is especially important in the current Portuguese tagset because several summary variables overlap with one another. The primary TMDA model therefore uses only specific linguistic variables.

### 2.2 `wcount` is excluded from factor extraction

The script imports `wcount`, but excludes it before factor analysis:
```sas
DROP = wcount v900-v919
```
This is correct because `wcount` is useful for descriptive corpus-size reporting but should not be treated as a factor-loading linguistic feature in the main MDA model.

### 2.3 Zero-variance variables are removed before factor analysis

A zero-variance filtering step was added before the first `PROC FACTOR`.

This was necessary because some variables had no usable variance in the analysis matrix and caused a singular-correlation-matrix error. The final script now detects variables with standard deviation equal to zero or missing and removes them before unrotated factor analysis.

The zero-variance variables are also exported for documentation in:
```text
zero_variance_dropped.csv
```
This step is important because `PROC FACTOR` requires a usable correlation matrix. Variables with zero variance cannot be meaningfully correlated and can cause factor extraction to fail.

### 2.4 Low-communality filtering starts from the zero-variance-filtered dataset

The low-communality removal now starts from the cleaned factor-input dataset, not directly from the summary-free dataset.

The effective sequence is:
```text
full imported data
→ remove wcount and v900-v919
→ remove zero-variance variables
→ run unrotated factor analysis
→ remove low-communality variables
→ run final rotated factor analysis
```
This ordering is correct.

### 2.5 The promax rotated factor pattern is used

The script extracts:
```sas
_TYPE_="PATTERN"
```
from the rotated `PROC FACTOR` output.

This is the appropriate choice for a promax-rotated factor analysis because promax is an oblique rotation. The rotated factor pattern is the matrix used for factor interpretation and scoring.

Earlier inherited scripts used `PREROTAT`, but `PREROTAT` refers to the pre-rotation solution and is not appropriate for interpreting the final promax-rotated structure.

### 2.6 Scoring now uses the same feature set as the final factor model

Section 7 now standardizes:
```sas
&project._sum_check
```
rather than the full metadata dataset.

This is preferable because `&project._sum_check` excludes:

- `wcount`;
- summary variables `v900-v919`;
- zero-variance variables;
- low-communality variables.

This ensures that scoring is aligned with the final factor model and avoids warnings from attempting to standardize variables deliberately removed from factor extraction.

### 2.7 Outliers are identified but retained

Section 8 is framed as:
```text
SECTION 8: OUTLIER IDENTIFICATION FOR DIAGNOSTIC INSPECTION
```
The script identifies outliers and exports them, but the active bypass restores the full scored dataset:
```sas
data &project._no_outliers;
    set scores_combined;
run;
```
Therefore, despite the internal dataset name `&project._no_outliers`, the final Section 9 analyses use the **full scored corpus**, including outliers.

This is intentional and supports the interpretation workflow, since the strongest examples of factor poles may legitimately be statistical outliers.

---

## 3. Review by script section

## Section 1 — Environment setup and macro variables

### Current status

This section defines the project, folder, SAS username, base path, and key analysis parameters.

The current factor model extracts:
```sas
%let extractfactors = 9 ;
```
and defines the factor score variables as:
```sas
%let factorvars = f1-f&extractfactors ;
```
The loading threshold and communality threshold are:
```sas
%let minloading = .3 ;
%let communalcutoff = .15 ;
```
### Assessment

This section is correct.

### Remaining limitation

The loading-selection logic in Section 6 is hard-coded for exactly nine factors. This is acceptable because the current model extracts nine factors, but if `&extractfactors` is changed, Section 6 must also be revised.

---

## Section 2 — Data ingestion

### Current status

The import macro expects TSV files with this structure:
```text
filename    subcorpus    wcount    v001 ... v006    v007_1-v007_4    v008-v230    v900-v919
```
The input statement reads:
```sas
filename
subcorpus
wcount
v001-v006
v007_1-v007_4
v008-v230
v900-v919
```
### Assessment

This section is correct, provided that all TSV headers match the expected column order.

The script ran successfully, so the current input structure is operationally valid in the working SAS environment.

---

## Section 3 — Base corpus preparation and initial exports

### Current status

The script combines four subcorpora into a single base dataset:

- `maiores_notas`;
- `menores_notas`;
- `menores_notas_gemini`;
- `menores_notas_gpt`.

The combined dataset is copied to the project dataset and exported as an initial CSV.

### Assessment

This section is correct.

### Methodological note

The variable `subcorpus` is central to the later statistical comparisons. It distinguishes higher-scoring human compositions, lower-scoring human compositions, and generated compositions.

---

## Section 3A — Summary-variable, metadata-variable, and zero-variance handling

### Current status

The script first creates a summary-free and metadata-filtered dataset by dropping:
```text
wcount
v900-v919
```
Then it computes standard deviations for all remaining numeric variables and identifies variables whose standard deviation is zero or missing.

Those variables are removed before the first factor analysis.

### Assessment

This section is correct and necessary.

### Importance

This step resolves the singular-correlation-matrix problem that occurred when zero-variance variables were still present in the factor-analysis matrix.

The zero-variance filtering makes the factor-analysis input more stable and reproducible.

---

## Section 4 — Unrotated factor analysis and communality cutoff

### Current status

The unrotated factor analysis now uses:
```sas
&project._factor_input
```
This dataset excludes:

- `wcount`;
- `v900-v919`;
- zero-variance variables.

Variables with communalities below the cutoff are then removed from this cleaned dataset.

### Assessment

This section is methodologically sound.

### Positive features

- Summary variables do not enter factor extraction.
- `wcount` does not enter factor extraction.
- Zero-variance variables are removed before factor analysis.
- Low-communality variable removal is guarded against empty macro variables.

### Reporting note

The communality cutoff should be reported because it affects the final feature set:
```text
communalcutoff = .15
```
---

## Section 5 — Preliminary rotated factor analysis

### Current status

This section runs a diagnostic promax-rotated factor analysis on the low-communality-filtered dataset.

The rotated factor pattern is extracted using:
```sas
_TYPE_="PATTERN"
```
### Assessment

This section is correct.

### Methodological role

This section is retained as a diagnostic step and as a future intervention point. In the current version, no additional variable-selection procedure is performed after this preliminary rotated solution.

This is consistent with the decision not to reintroduce summary variables into the primary TMDA model.

---

## Section 6 — Final rotated factor analysis and loadings table

### Current status

The final factor analysis uses:
```sas
rotate=promax
```
The script extracts the rotated factor pattern using:
```sas
_TYPE_="PATTERN"
```
The loading-selection logic assigns each variable to its strongest factor if its absolute loading meets or exceeds:
```text
.30
```
The script then creates:

- `rotated.csv`;
- `loadtable.html`;
- `loadtable_for_interpretation.html`;
- `loadtable_for_interpretation.csv`.

### Assessment

This section is correct for the current nine-factor model.

### Important note on `PATTERN`

Because promax is an oblique rotation, the rotated factor pattern should be used for interpretation and scoring. The current use of `_TYPE_="PATTERN"` is therefore appropriate.

### Remaining limitation

The loading-selection block is hard-coded for factors 1 through 9. This is fine for the current analysis, but the block must be revised if a different number of factors is extracted.

---

## Section 6A — Feature labels

### Current status

The script defines a `$featurelabels` format mapping Portuguese tagset variable names to readable descriptions.

### Assessment

This section is correct.

The labels correspond to the Portuguese tagset variable structure and allow loadings tables to be interpreted more easily.

---

## Section 6B — Loadings tables

### Current status

The script prints positive and negative loading tables by factor and creates a combined interpretation table.

Temporary table cleanup is now protected with short macro names that comply with SAS macro-name length limits.

### Assessment

This section is correct.

### Notes

The previous macro names were too long for SAS. They have been shortened, resolving the macro compilation issue.

The cleanup logic now avoids attempting to delete non-existent temporary tables.

---

## Section 7 — Scoring

### Current status

The script now standardizes:
```sas
&project._sum_check
```
This dataset is the final feature set used in the factor model.

The factor-score matrix is built from loaded variables, and factor scores are computed for all texts.

The main score outputs are:
```text
cl_st1_ph3_ednalvo_scores.csv
cl_st1_ph3_ednalvo_scores_only.csv
```
### Assessment

This section is now correct.

### Important improvement

Earlier versions standardized the full metadata dataset, which still included excluded zero-variance variables. The final version standardizes the same feature set used in the final factor model, eliminating unnecessary warnings and improving methodological alignment.

### Main output for ranking

The key ranking file is:
```text
cl_st1_ph3_ednalvo_scores_only.csv
```
It contains:
```text
filename
subcorpus
f1-f9
```
and is suitable for ranking compositions by factor pole.

---

## Section 8 — Outlier identification for diagnostic inspection

### Current status

The script identifies factor-score outliers using an IQR rule:
```text
lower fence = Q1 - 1 * IQR
upper fence = Q3 + 1 * IQR
```
Factor-specific outlier files are exported as:
```text
outliers_f1.csv
outliers_f2.csv
...
outliers_f9.csv
```
The combined outlier list is exported as:
```text
outliers_all.csv
```
### Assessment

This section is correct and aligned with the intended interpretation workflow.

### Important interpretation

The outliers are **not removed** from the final analysis because the bypass is intentionally active.

This means outliers are:

- identified;
- exported;
- retained in score files;
- retained in ANOVAs;
- retained in boxplots;
- available for ranking and qualitative inspection.

This is appropriate because extreme texts may be strong exemplars of factor poles.

---

## Section 9 — Statistical analysis

### Current status

The script compares factor scores across:
```sas
subcorpus
```
For each factor, it runs:
```sas
model f&i = subcorpus;
```
and exports:
```text
r2_subcorpus_f&i.csv
anova_subcorpus_f&i.csv
means_subcorpus_f&i.csv
```
It also generates boxplots by subcorpus.

### Assessment

This section is correct.

### Important interpretation

Because the outlier bypass is active, ANOVAs and boxplots use the full scored corpus, including outliers.

This should be reported explicitly.

Suggested wording:

> Factor-score outliers were identified using an IQR rule for diagnostic inspection, but were retained in the primary statistical comparisons and in the ranking of representative texts.

---

## Final zip and cleanup block

### Current status

The script zips the project output and then deletes top-level `.png`, `.html`, `.tsv`, and `.csv` files from the project folder.

### Assessment

This is operationally acceptable.

### Caution

Because the cleanup step removes top-level output files after zipping, users should retrieve outputs from the zip archive unless the cleanup block is disabled during development.

The cleanup step scans only the top-level project folder, not subdirectories.

---

## 4. Final methodological status

| Component                     | Current decision                                                  | Assessment                           |
|-------------------------------|-------------------------------------------------------------------|--------------------------------------|
| Main factor variables         | Specific variables only                                           | Correct                              |
| Summary variables `v900-v919` | Excluded from factor extraction                                   | Correct                              |
| `wcount`                      | Imported, reported descriptively, excluded from factor extraction | Correct                              |
| Zero-variance variables       | Detected, exported, and removed before factor analysis            | Correct                              |
| Low-communality filtering     | Applied after zero-variance filtering, cutoff `.15`               | Correct                              |
| Rotation                      | Promax                                                            | Appropriate                          |
| Rotated matrix used           | `PATTERN`                                                         | Correct                              |
| Scoring input                 | Same feature set as final factor model                            | Correct                              |
| Number of factors             | 9                                                                 | Correct for current hard-coded logic |
| Outliers                      | Identified, exported, retained                                    | Correct for interpretation workflow  |
| Statistical comparison        | Factor scores by `subcorpus`                                      | Correct                              |
| Ranking file                  | `cl_st1_ph3_ednalvo_scores_only.csv`                              | Correct                              |

---

## 5. Recommended interpretation workflow

This is the recommended workflow after each full SAS run.

## Step 1 — Start with the factor interpretation table

Open:
```text
loadtable_for_interpretation.csv
```
For each factor, inspect:

- primary positive loadings;
- primary negative loadings;
- secondary loadings, if relevant.

The goal is to identify clusters of linguistic features that define each pole.

The factor interpretation should be based on the actual loading table, not only on variable labels.

---

## Step 2 — Rank compositions using the full scores file

Use:
```text
cl_st1_ph3_ednalvo_scores_only.csv
```
For each factor:

### Positive pole

Sort descending by the factor score.

Example:
```text
sort f1 from highest to lowest
```
The highest texts are the strongest positive-pole candidates.

### Negative pole

Sort ascending by the factor score.

Example:
```text
sort f1 from lowest to highest
```
The lowest texts are the strongest negative-pole candidates.

Repeat for:
```text
f1, f2, ..., f9
```
---

## Step 3 — Check whether top-ranked compositions are outliers

For each factor, open the corresponding diagnostic outlier file:
```text
outliers_f1.csv
outliers_f2.csv
...
outliers_f9.csv
```
Then check whether the strongest ranked examples from `cl_st1_ph3_ednalvo_scores_only.csv` appear in that factor’s outlier file.

| Ranking result                                                          | Outlier status         | How to interpret                                      |
|-------------------------------------------------------------------------|------------------------|-------------------------------------------------------|
| Top-ranked text does not appear in `outliers_f&i.csv`                   | Not an outlier         | Strong representative example                         |
| Top-ranked text appears in `outliers_f&i.csv` with high positive score  | Positive-pole outlier  | Extreme positive exemplar; inspect carefully          |
| Top-ranked text appears in `outliers_f&i.csv` with large negative score | Negative-pole outlier  | Extreme negative exemplar; inspect carefully          |
| Many top examples are outliers                                          | Concentrated extremity | Factor may be shaped by a small set of extreme texts  |
| Outlier seems linguistically coherent                                   | Genuine extreme        | Can be used as an illustrative strong case            |
| Outlier seems caused by annotation/counting problem                     | Artifact               | Treat cautiously or exclude from qualitative examples |

---

## Step 4 — Inspect the actual compositions

For each top-ranked text, use:
```text
filename
subcorpus
```
to locate the corresponding composition.

Likely locations are:
```text
corpus/01_composicoes/<subcorpus>/<filename>
```
and/or the annotated version:
```text
corpus/03_composicoes_anotadas/<subcorpus>/<filename>
```
For generated compositions, the original generated text may be a Markdown file, while the annotated version may be a `.txt` file.

When inspecting, compare:

1. the factor score;
2. the factor pole;
3. the high-loading linguistic features;
4. the actual text;
5. the annotation counts, if needed.

---

## Step 5 — Select examples for interpretation

For each factor pole, select examples from three categories if possible:

### A. Strong non-outlier examples

These are often the safest representative examples.

### B. Extreme but linguistically coherent outliers

These are useful for illustrating the maximum expression of a factor pole.

### C. Borderline or ambiguous examples

These help define the boundary of the factor interpretation.

A good qualitative interpretation should not rely on a single extreme text. Ideally, inspect several top-ranked examples per pole.

---

## Step 6 — Compare subcorpora

Use the ANOVA and means outputs:
```text
anova_subcorpus_f&i.csv
means_subcorpus_f&i.csv
r2_subcorpus_f&i.csv
```
and the boxplots:
```text
boxplot_f1.png
boxplot_f2.png
...
boxplot_f9.png
```
For each factor, ask:

1. Which subcorpus has the highest mean?
2. Which subcorpus has the lowest mean?
3. Are the differences statistically visible in ANOVA?
4. Are group differences driven by a few extreme texts?
5. Do generated compositions cluster differently from human-written compositions?
6. Do high-score and low-score human compositions differ on the factor?

---

## Step 7 — Use outliers diagnostically, not mechanically

Because the outlier bypass is active, outliers are retained.

The best use of outlier files is to ask:

- Is this text genuinely an extreme example of the factor?
- Does the text have unusual structure, length, or genre?
- Is the extremity caused by repeated linguistic features?
- Is the annotation credible?
- Are outliers concentrated in one subcorpus?
- Are LLM-generated texts producing unusual factor profiles?

This turns outliers into interpretive evidence rather than treating them as automatic noise.

---

## 6. Recommended reporting language

The current methodological position can be described as follows:

> The analysis used normalised document-feature matrices for four subcorpora. Aggregate summary variables were excluded from factor extraction to avoid redundancy with their component variables and to reduce artificial covariance caused by overlapping summary categories. The word-count variable was retained for descriptive corpus-size reporting but excluded from factor analysis. Zero-variance variables were identified and removed before factor extraction to avoid singularity in the correlation matrix. After an initial unrotated factor analysis, variables below the communality cutoff were removed. A final principal factor analysis with promax rotation was then performed, and the rotated factor pattern was extracted using `_TYPE_="PATTERN"`. Factor scores were computed using the same feature set retained in the final factor model. Factor-score outliers were identified using an IQR rule and exported for diagnostic qualitative inspection, but were retained in the main score files, statistical comparisons, and selection of representative texts. Representative compositions for each factor pole were selected by ranking the full factor-score file and cross-checking top-ranked texts against the factor-specific outlier lists.

---

## 7. Remaining minor caveats

### 7.1 Hard-coded nine-factor logic

The script currently assumes exactly nine factors in the loading-selection logic.

This is fine as long as:
```sas
%let extractfactors = 9 ;
```
remains unchanged.

If the number of extracted factors changes, Section 6 must be revised.

### 7.2 Outlier filenames

The files:
```text
outliers_f1.csv
outliers_f2.csv
...
outliers_f9.csv
```
are diagnostic files. They do not mean the listed observations were removed from the final analysis.

### 7.3 Cleanup after zipping

If immediate access to CSV, HTML, or PNG files is needed after the SAS run, the cleanup block may need to be temporarily disabled.

Otherwise, outputs should be retrieved from the zip archive.

### 7.4 TSV input path

The import macro expects the TSV files to be available at the path referenced by:
```sas
&whereisit/&myfolder/&infile
```
Because the programme now runs successfully, the current location is valid in the SAS environment. If the TSV files are moved, the `INFILE` path should be updated accordingly.

---

## 8. Final verdict

The final SAS script is **ready for use** for the current nine-factor TMDA workflow.

It is aligned with the methodological decisions made during revision:

- summary variables are excluded from factor extraction;
- `wcount` is retained descriptively but excluded from factor extraction;
- zero-variance variables are removed before factor analysis;
- low-communality variables are removed after the unrotated solution;
- promax rotation is interpreted through the rotated factor pattern;
- factor scoring uses the same feature set as the final factor model;
- outliers are identified for inspection but retained for ranking and statistical analysis.

The key final position is:

> Outliers are identified for inspection, but retained for ranking and final statistical analysis.

This is defensible for MDA because the strongest factor-pole texts are often exactly the texts that appear statistically extreme. The important analytical step is therefore not to discard them automatically, but to inspect them carefully and document whether they are genuine extreme exemplars or possible annotation/counting artifacts.
