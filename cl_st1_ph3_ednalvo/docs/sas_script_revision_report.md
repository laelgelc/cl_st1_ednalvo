# Full Report on the SAS Script Revision

## 1. Overall assessment

The SAS script is now in a **methodologically coherent and operationally usable state**, especially given the explicit decision to **keep the outlier bypass active**.

The current workflow is clear:

1. Import the normalized DFM TSV files.
2. Combine all four subcorpora.
3. Exclude metadata and aggregate variables from factor extraction.
4. Run unrotated factor analysis.
5. Remove low-communality variables.
6. Run final rotated factor analysis.
7. Generate loadings tables and interpretation tables.
8. Score all compositions.
9. Identify factor-score outliers for diagnostic inspection.
10. Keep all outliers in the final score and statistical-analysis datasets.
11. Run ANOVAs and boxplots by `subcorpus`.
12. Zip output files.

Given your intended downstream workflow — ranking the strongest compositions per factor pole using `&project._scores_only.csv` — keeping the outlier bypass active is justified.

---

# 2. Main methodological decisions now implemented

## 2.1 Summary variables are excluded from factor extraction

The script now excludes the aggregate variables:

```
v900-v919
```


from factor extraction.

This is methodologically appropriate because those variables are derived from lower-level variables and, if included together with their components, could create artificial covariance and overweight broad linguistic domains.

The script now uses the specific linguistic variables as the main input to factor analysis. This is the safest approach for the current Portuguese tagset, especially because several summary variables overlap with one another.

## 2.2 `wcount` is excluded from factor extraction

The script now reads `wcount` during import but drops it before factor analysis:

```
DROP = wcount v900-v919
```


This is correct.

`wcount` is useful for descriptive reporting, but it should not be treated as a factor-loading linguistic feature in the main MDA model.

## 2.3 Rotated factor pattern is used

The script now extracts:

```
_TYPE_="PATTERN"
```


from the rotated `PROC FACTOR` output.

This is important because the loadings, interpretation tables, and scoring coefficients should be based on the rotated factor pattern, not the pre-rotated solution.

This correction makes the factor interpretation much more appropriate.

## 2.4 Outliers are identified but retained

Section 8 has been reframed as:

```
SECTION 8: OUTLIER IDENTIFICATION FOR DIAGNOSTIC INSPECTION
```


This is now conceptually aligned with your workflow.

The script identifies outliers and exports them, but the active bypass restores the full scored dataset:

```
data &project._no_outliers;
    set scores_combined;
run;
```


Therefore, despite the internal dataset name `&project._no_outliers`, the final Section 9 analyses use the **full scored corpus**, including outliers.

That is acceptable as long as this is clearly documented, which it now is.

---

# 3. Review by script section

## Section 1 — Environment setup and macro variables

### Current status

This section is mostly fine.

It defines:

```
%let project = cl_st1_ph3_ednalvo ;
%let myfolder = &project ;
%let sasusername = u63529080 ;
%let whereisit = /home/&sasusername ;
```


and sets:

```
%let extractfactors = 9 ;
%let factorvars = f1-f&extractfactors ;
%let minloading = .3 ;
%let communalcutoff = .15 ;
```


### Comment

The only remaining caution is that the loading-selection logic in Section 6 is hard-coded for exactly nine factors. This is fine because `extractfactors` is currently set to 9, but if you later change that number, Section 6 must be revised.

### Recommendation

Add a short comment near the macro variable definition:

```
/* NOTE: Section 6 currently contains loading-selection logic hard-coded
   for exactly 9 factors. If &extractfactors changes, revise Section 6. */
```


This is not required for execution, but useful for reproducibility.

---

## Section 2 — Data ingestion

### Current status

The import macro now expects the TSV structure:

```plain text
filename    subcorpus    wcount    v001 ... v230    v900-v919
```


This is consistent with the revised input statement:

```
INPUT
    filename :$150.
    subcorpus :$50.
    wcount
    v001-v006
    v007_1-v007_4
    v008-v230
    v900-v919
;
```


### Assessment

This section is correct **provided that** all TSV files actually have `wcount` as the third column.

### Recommendation

Before final production runs, quickly verify that each TSV header begins with:

```plain text
filename    subcorpus    wcount    v001
```


If yes, the import block is good.

---

## Section 3 — Base corpus preparation and initial exports

### Current status

The script combines the four subcorpora into `base_corpus`, then copies it to the project dataset.

This is coherent.

The script also exports the combined dataset:

```
&project..csv
```


### Assessment

This section is fine.

### Methodological note

The combined dataset includes:

- original high-score compositions;
- original low-score compositions;
- Gemini-generated compositions;
- GPT-generated compositions.

The variable `subcorpus` is therefore central to later statistical comparisons.

---

## Section 4 — Unrotated factor analysis and communality cutoff

### Current status

The input dataset now excludes:

- `wcount`;
- `v900-v919`.

The unrotated factor analysis uses:

```
var _NUMERIC_;
```


Because metadata and summary variables have already been removed, this is now acceptable.

### Assessment

This section is methodologically sound.

### Positive changes already made

- `wcount` no longer contaminates the factor model.
- Summary variables do not enter factor extraction.
- Low-communality variable selection is guarded against empty macro variables.

### Comment

The communality cutoff is:

```
%let communalcutoff = .15 ;
```


This is a reasonable threshold, but should be reported in the methods section because it affects which variables remain in the final rotated model.

---

## Section 5 — Preliminary rotated factor analysis

### Current status

This section runs a preliminary rotated factor analysis on:

```
&project._no_low_c
```


It now extracts:

```
_TYPE_="PATTERN"
```


### Assessment

This is correct.

### Methodological role

This section is currently diagnostic. It does not perform additional variable selection. That is fine, because the current conservative approach is:

1. remove summary variables;
2. remove low-communality variables;
3. do not reintroduce summary variables.

This is coherent with the decision not to risk summary-variable overlap.

---

## Section 6 — Final rotated factor analysis and loadings table

### Current status

The final `PROC FACTOR` uses:

```
rotate=promax
```


and the script now uses:

```
_TYPE_="PATTERN"
```


for the rotated factor pattern.

This is correct.

### Loadings logic

The script identifies the strongest factor for each variable by comparing the absolute values of `factor1` through `factor9`, and then assigns:

- `factor = 'f1'`, `'f2'`, etc.;
- `pole = 1` or `-1`;
- `loaded = 1`.

### Assessment

This is valid **as long as the model uses exactly 9 factors**.

### Remaining limitation

The logic is hard-coded for nine factors. This is not a problem now, but it should be documented.

### Loadings interpretation

The output files:

```plain text
rotated.csv
loadtable_for_interpretation.csv
```


are important outputs for interpreting each factor. The labeling format now matches the Portuguese tagset variable names, which is appropriate.

---

## Section 7 — Scoring

### Current status

The script standardizes the full project dataset:

```
PROC STDIZE DATA=&project._meta METHOD=STD OUT=mdz OUTSTAT=meta_stats;
    var _NUMERIC_ ;
RUN;
```


Then it builds the score coefficient matrix from variables that loaded at or above the threshold.

It exports:

```plain text
&project._scores.csv
&project._scores_only.csv
```


### Assessment

This section is acceptable.

### Important note about `wcount`

Although `wcount` is standardized in `mdz`, it should not affect factor scoring because the scoring matrix is based on the variables in `rotated4`, which comes from the factor-loading variables. Since `wcount` was excluded before factor extraction, it should not appear in `score`.

So this is operationally acceptable.

### Main output for later ranking

Your key file remains:

```plain text
&project._scores_only.csv
```


This file contains:

```plain text
filename, subcorpus, f1, f2, ..., f9
```


and is suitable for ranking compositions by factor pole.

---

## Section 8 — Outlier identification for diagnostic inspection

### Current status

This section now correctly describes the intended logic:

- outliers are identified;
- outlier lists are exported;
- outliers are retained in the final analysis because the bypass is active.

The factor-specific exports are now named more clearly:

```plain text
outliers_f1.csv
outliers_f2.csv
...
outliers_f9.csv
```


This is better than the previous `outliers_deleted_f&i..csv` naming.

### Assessment

This section is now coherent with your interpretive goals.

### What the outlier files mean

Each `outliers_f&i.csv` file contains compositions whose score on factor `f&i` lies outside the IQR fences:

```plain text
lower fence = Q1 - 1 * IQR
upper fence = Q3 + 1 * IQR
```


Because `multipl=1`, the outlier definition is stricter than the common 1.5×IQR rule.

### Important interpretation

These outliers are **not removed** from the final dataset. They are exported only to support diagnostic review.

That is appropriate because, in MDA interpretation, extreme texts may be the best examples of a factor pole.

---

## Section 9 — Statistical analysis

### Current status

Section 9 now compares factor scores across:

```
subcorpus
```


rather than `prompt`.

This is correct for the current data structure.

The script runs:

```
model f&i = subcorpus;
```


for each factor.

It exports:

```plain text
r2_subcorpus_f1.csv
anova_subcorpus_f1.csv
means_subcorpus_f1.csv
...
```


and produces boxplots by `subcorpus`.

### Assessment

This section is now conceptually correct.

### Important interpretation

Because the outlier bypass is active, these ANOVAs and boxplots are based on **all scored compositions**, including outliers.

That is acceptable, but it should be reported clearly.

Suggested wording for methods/reporting:

> Factor-score outliers were identified using an IQR rule for diagnostic inspection, but were retained in the primary statistical comparisons and in the ranking of representative texts.

---

## Final zip and cleanup block

### Current status

The script zips the project output and then deletes top-level `.png`, `.html`, `.tsv`, and `.csv` files in the project folder.

### Assessment

This is operationally plausible, but still slightly risky.

### Caution

The cleanup step may remove top-level output CSVs after they are zipped. That is fine if you intend to retrieve outputs from the zip file, but it may be confusing if you expect the CSVs to remain visible after the run.

### Recommendation

If you want to inspect outputs immediately after the SAS run, either:

- open them from the zip file; or
- temporarily disable the cleanup block.

Also, the cleanup comment still says:

```
Delete all png, html, tsv, and csv files after zipping
```


but the code only scans the top-level project folder, not subdirectories. A clearer comment would be:

```
/* Delete top-level png, html, tsv, and csv files after zipping.
   This cleanup does not recursively delete files in subdirectories. */
```


---

# 4. Final methodological status

## The script now implements this analytical model

| Component                     | Current decision                             | Assessment                      |
|-------------------------------|----------------------------------------------|---------------------------------|
| Main factor variables         | Specific variables only                      | Correct                         |
| Summary variables `v900-v919` | Excluded from factor extraction              | Correct                         |
| `wcount`                      | Imported but excluded from factor extraction | Correct                         |
| Rotation                      | Promax                                       | Appropriate                     |
| Rotated matrix used           | `PATTERN`                                    | Correct                         |
| Low-communality filtering     | Yes, cutoff `.15`                            | Acceptable                      |
| Number of factors             | 9                                            | Fine, but hard-coded downstream |
| Outliers                      | Identified, exported, retained               | Correct for your workflow       |
| Statistical comparison        | Factor scores by `subcorpus`                 | Correct                         |
| Ranking file                  | `&project._scores_only.csv`                  | Correct                         |

---

# 5. Recommended interpretation workflow

This is the workflow I recommend using after each full SAS run.

## Step 1 — Start with the factor interpretation table

Open:

```plain text
loadtable_for_interpretation.csv
```


For each factor, inspect:

- primary positive loadings;
- primary negative loadings;
- secondary loadings, if relevant.

You are looking for clusters of linguistic features that define each pole.

For example:

- Factor 1 positive pole: high loadings on certain noun/adjective/subordination features.
- Factor 1 negative pole: high negative loadings on conversational or informal features.

The exact interpretation should come from the actual loading table, not from the variable labels alone.

---

## Step 2 — Rank compositions using the full scores file

Use:

```plain text
&project._scores_only.csv
```


For each factor:

### Positive pole

Sort descending by the factor score.

Example:

```plain text
sort f1 from highest to lowest
```


The highest texts are the strongest positive-pole candidates.

### Negative pole

Sort ascending by the factor score.

Example:

```plain text
sort f1 from lowest to highest
```


The lowest texts are the strongest negative-pole candidates.

Repeat for:

```plain text
f1, f2, ..., f9
```


---

## Step 3 — Check whether top-ranked compositions are outliers

For each factor, open the corresponding diagnostic outlier file:

```plain text
outliers_f1.csv
outliers_f2.csv
...
outliers_f9.csv
```


Then check whether the strongest ranked examples from `&project._scores_only.csv` appear in that factor’s outlier file.

Interpretation:

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

```plain text
filename
subcorpus
```


to locate the corresponding composition.

Likely locations are:

```plain text
corpus/01_composicoes/<subcorpus>/<filename>
```


and/or the annotated version:

```plain text
corpus/03_composicoes_anotadas/<subcorpus>/<filename>
```


For generated compositions, the original generated text may be a Markdown file, while the annotated version may be a `.txt` file.

When inspecting, compare:

1. the factor score;
2. the factor pole;
3. the high-loading linguistic features;
4. the actual text;
5. the annotation counts if needed.

---

## Step 5 — Select examples for interpretation

For each factor pole, select examples from three categories if possible:

### A. Strong non-outlier examples

These are often the safest representative examples.

### B. Extreme but linguistically coherent outliers

These are useful for illustrating the maximum expression of a factor pole.

### C. Borderline or ambiguous examples

These help you understand the boundary of the factor interpretation.

A good qualitative interpretation should not rely only on one extreme text. Ideally, inspect several top-ranked examples per pole.

---

## Step 6 — Compare subcorpora

Use the ANOVA and means outputs:

```plain text
anova_subcorpus_f&i.csv
means_subcorpus_f&i.csv
r2_subcorpus_f&i.csv
```


and the boxplots:

```plain text
boxplot_f1.png
boxplot_f2.png
...
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

Because your bypass is active, outliers are not excluded. This is appropriate.

The best use of outlier files is to ask:

- Is this text genuinely an extreme example of the factor?
- Does the text have unusual structure, length, or genre?
- Is the extremity caused by repeated linguistic features?
- Is the annotation credible?
- Are outliers concentrated in one subcorpus?
- Are LLM-generated texts producing unusual factor profiles?

This turns outliers into interpretive evidence rather than treating them as automatic noise.

---

# 6. Recommended reporting language

You can describe the procedure like this:

> The analysis used normalized document-feature matrices for four subcorpora. Aggregate summary variables were excluded from factor extraction to avoid redundancy with their component variables and to reduce artificial covariance caused by overlapping summary categories. The word-count variable was retained for descriptive corpus-size reporting but excluded from factor analysis. After an initial unrotated factor analysis, variables below the communality cutoff were removed. A final principal factor analysis with promax rotation was then performed, and factor scores were computed for all texts. Factor-score outliers were identified using an IQR rule and exported for diagnostic qualitative inspection, but were retained in the main score files, statistical comparisons, and selection of representative texts. Representative compositions for each factor pole were selected by ranking the full factor-score file and cross-checking top-ranked texts against the factor-specific outlier lists.

---

# 7. Remaining minor caveats

## 7.1 Hard-coded nine-factor logic

The script currently assumes exactly 9 factors in Section 6.

This is fine as long as:

```
%let extractfactors = 9 ;
```


remains unchanged.

If you change the number of factors, the loading-selection logic must be revised.

## 7.2 Outlier filenames

The new names:

```plain text
outliers_f&i..csv
```


are appropriate.

They correctly indicate that the files contain diagnostic outlier lists, not necessarily deleted texts.

## 7.3 Cleanup after zipping

If you need immediate access to the CSV/HTML/PNG files after the SAS run, be aware that the cleanup block may remove top-level copies after zipping.

You may want to inspect the zip file directly or temporarily disable cleanup during development.

---

# 8. Final verdict

With the outlier bypass intentionally active, the script is now **methodologically consistent** with your interpretive workflow.

The key final position is:

> Outliers are identified for inspection, but retained for ranking and final statistical analysis.

This is a defensible choice for MDA, because the strongest factor-pole texts are often exactly the texts that appear statistically extreme. The important thing is not to delete them automatically, but to inspect them carefully and document whether they are genuine extreme exemplars or possible annotation/counting artifacts.