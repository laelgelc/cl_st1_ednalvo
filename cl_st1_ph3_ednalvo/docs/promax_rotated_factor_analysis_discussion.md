# Promax Rotated Factor Analysis Discussion

> **User:** Considering what we have discussed on the promax rotated factor analysis for `cl_st1_ph3_ednalvo.sas`, I found that `PATTERN` was also adopted for the Lexical Multi-Dimensional Analysis (LMDA) in `cl_st1_ph2_andrea.sas` contrasting with the original `ednalvo` SAS script and the SAS script from the reference project `cl_st1_ph2_sara.sas`. In the case of the LMDA script, I remember Professor Tony once commented that he had changed from `PREROTAT` to `PATTERN`. `sara`'s script did not incorporate that change because it was based on a rather old reference. Do you think that what holds true for LMDA is applicable to TMDA with regard to promax rotated factor analysis?

Yes — I think the same principle **does apply to TMDA** when the factor analysis uses **promax rotation**. In fact, the argument for using `PATTERN` is not specific to LMDA vs. TMDA; it follows from the nature of **oblique rotation** in `PROC FACTOR`.

## Short answer

For a **promax-rotated factor analysis**, whether in **LMDA** or **TMDA**, the appropriate matrix for interpreting the rotated factors is normally the **rotated factor pattern**, i.e.:

```
_TYPE_ = "PATTERN"
```


So, yes: if Professor Tony changed LMDA from `PREROTAT` to `PATTERN` because the analysis uses promax rotation, that reasoning should also hold for TMDA using promax rotation.

---

## Why this is not LMDA-specific

The difference between LMDA and TMDA is mainly the kind of features being analyzed:

| Analysis type | Typical variables                                                       |
|---------------|-------------------------------------------------------------------------|
| LMDA          | lexical/keyword variables                                               |
| TMDA          | grammatical, syntactic, discourse, stance, or linguistic feature counts |

But the **factor-analytic mechanics** are the same once you use:

```
rotate=promax
```


Promax is an **oblique rotation**, meaning that factors are allowed to correlate. In an oblique solution, SAS outputs multiple relevant matrices, including:

- the **pattern matrix**;
- the **structure matrix**;
- factor correlations;
- possibly pre-rotation/unrotated information.

The key point is that, for oblique rotation, the **pattern matrix** is usually the matrix used to define which variables belong to which factor.

---

## Why `PREROTAT` is not appropriate for interpreting the rotated solution

The name `PREROTAT` is already a warning: it refers to the factor pattern **before rotation**.

If your final analytical model is:

```
rotate=promax
```


then the substantive interpretation should be based on the **post-rotation** solution.

Using `PREROTAT` after asking SAS for a rotated solution would mean that the script is extracting the pre-rotation loadings, even though the intended model is rotated. That can cause a mismatch:

- the SAS output visually reports the rotated solution;
- the script extracts pre-rotated values;
- the loadings table is not aligned with the intended rotated factor interpretation;
- scoring coefficients may be based on the wrong pattern of variable–factor association.

So `PREROTAT` is not just an older convention; in this context it can produce the wrong interpretation.

---

## Why `PATTERN` is the better choice for promax

For oblique rotation, the **pattern matrix** gives the unique contribution of each variable to each factor, controlling for correlations among factors. This is typically the matrix used to assign variables to factors and interpret factor dimensions.

In practical MDA terms, `PATTERN` answers:

> Which variables define this factor after rotation?

That is exactly what you need when creating:

- loading tables;
- positive/negative pole interpretation;
- primary and secondary loading assignments;
- scoring coefficients based on loaded variables.

So for both LMDA and TMDA, if you use promax, `PATTERN` is the more defensible choice.

---

## Important nuance: pattern vs. structure

With oblique rotation, there is another possible matrix: the **structure matrix**. The structure matrix gives correlations between variables and factors. The pattern matrix gives regression-like coefficients representing the unique loading of a variable on a factor.

This distinction matters because, when factors correlate, a variable can correlate with more than one factor even if its unique loading is mainly on one factor.

For MDA interpretation, the usual preference is:

| Matrix              | Meaning                                        | Use                                              |
|---------------------|------------------------------------------------|--------------------------------------------------|
| Pattern matrix      | Unique association between variable and factor | Best for assigning variables to factors          |
| Structure matrix    | Correlation between variable and factor        | Useful as supplementary diagnostic               |
| Pre-rotated pattern | Loadings before rotation                       | Not appropriate for final rotated interpretation |

So `PATTERN` is still the right main choice.

---

## Why older scripts may have used `PREROTAT`

There are a few possible reasons:

1. **Historical inheritance**  
   Older scripts may have simply carried forward code from earlier templates.

2. **SAS output naming confusion**  
   `PROC FACTOR` output names can be unintuitive. It is easy to mistake `PREROTAT` for the rotated pattern if one is following older examples or partial documentation.

3. **Orthogonal vs. oblique ambiguity**  
   In orthogonal solutions, interpretation can feel more straightforward because factors are uncorrelated. In oblique solutions, SAS outputs several matrices, and users must decide which one represents the analytical target.

4. **Template reuse**  
   A reference script may have worked operationally for a previous project even if it was not ideal for later methodological decisions.

5. **Later correction**  
   If Professor Tony explicitly changed LMDA to `PATTERN`, that suggests a methodological update rather than an incidental coding preference.

---

## Applying this to your TMDA script

Since `cl_st1_ph3_ednalvo.sas` uses:

```
rotate=promax
```


the revised use of:

```
_TYPE_="PATTERN"
```


is appropriate in both places where you extract the rotated factor loadings:

1. the preliminary rotated solution;
2. the final rotated solution.

This is especially important in the final solution, because that output feeds:

- `rotated3`;
- `rotated4`;
- `loadtable.html`;
- `loadtable_for_interpretation.csv`;
- the factor scoring matrix;
- `&project._scores_only.csv`.

So the change is not cosmetic. It affects the whole interpretation/scoring pipeline.

---

## My recommendation

I would keep `PATTERN` in the TMDA script.

I would also document the decision briefly, because the existence of older reference scripts using `PREROTAT` may raise questions later.

Suggested methodological note:

> Because the final factor analysis uses promax rotation, factor interpretation and scoring are based on the rotated factor pattern (`_TYPE_="PATTERN"` in the SAS `OUTSTAT` dataset). Earlier reference scripts used `PREROTAT`, but this refers to the pre-rotation solution and is not appropriate for interpreting the final promax-rotated factor structure.

---

## Bottom line

Yes: **what holds for LMDA also holds for TMDA here**.

The choice between `PREROTAT` and `PATTERN` is not determined by whether the variables are lexical or grammatical. It is determined by the factor-analysis model, especially the use of **promax oblique rotation**.

For your revised TMDA script:

```
_TYPE_="PATTERN"
```


is the methodologically correct choice for the rotated factor pattern.
