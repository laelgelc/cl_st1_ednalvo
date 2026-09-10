# Summary Variables Overlap Discussion

> **User:** Before concluding the matter, I would like to discuss to which degree the overlap phenomenon could be harmful to the multidimensional analysis. Professor Tony said that, regarding the original Biber implementation (I do not know if there was any overlap back then), we should not have both a summary variable coexisting with specific variables. The decision-making seemed binary, towards the least worse end. What do you think?

Yes — I think Professor Tony’s point is methodologically sound, and it is especially important in **factor analysis / multidimensional analysis**.

The short version is:

> In MDA, it is generally risky to let a summary variable coexist with the specific variables from which it is computed, because that creates artificial covariance and can overweight the underlying linguistic phenomenon.

But the overlap issue makes your case more complicated than the original binary rule.

## Why summary + specific coexistence is harmful

Suppose you include both:

| variable | meaning        |
|----------|----------------|
| `v902`   | all nouns      |
| `v028`   | common nouns   |
| `v029`   | abstract nouns |
| `v030`   | concrete nouns |
| `v031`   | animate nouns  |
| etc.     | etc.           |

Since `v902` is partly or fully computed from the specific noun variables, it is not independent evidence. It is a linear or near-linear composite of them.

In factor analysis, that can cause several problems.

### 1. Artificially inflated correlations

If `v902` is the sum of `v027-v041`, then it will naturally correlate with many of those variables. That correlation is not an empirical discovery; it is built into the variable design.

So if the factor analysis finds that `v902`, `v028`, `v029`, and `v030` load together, that factor may partly reflect the arithmetic relationship among variables rather than an underlying discourse dimension.

### 2. Overweighting one linguistic domain

If you include both the general and specific forms, the same phenomenon enters the analysis multiple times.

For example:

```plain text
v902 = all nouns
v028 = common nouns
v029 = abstract nouns
v030 = concrete nouns
...
```


A text with many nouns will score high on the noun summary and on several noun subtypes. That gives “nouniness” extra weight in the correlation matrix compared with a feature that has only one variable.

This can distort factor extraction because the factor model may treat noun-related variation as more important simply because it is represented redundantly.

### 3. Multicollinearity or near-linear dependence

Strictly speaking, if the summary variable is exactly the sum of the specific variables, then there is linear dependence. In practice, because of overlapping tags, normalization, sparse variables, and annotation decisions, it may be only near-linear dependence.

Either way, this can make the factor solution less stable.

Potential symptoms:

- unstable loadings;
- Heywood cases;
- inflated communalities;
- factors dominated by one family of related variables;
- difficult interpretation;
- summary variables loading strongly simply because they mirror their components.

### 4. Ambiguous interpretation

If both `v904` and `v065` load on the same factor, what does that mean?

- More verbs generally?
- More modal verbs specifically?
- Or just a built-in relationship because modal verbs are included inside the general verb count?

That ambiguity weakens the linguistic interpretation of dimensions.

## Why the original Biber-style solution used a binary decision

The binary decision makes sense as a compromise:

> Either use the summary variable, or use its specific variables, but avoid using both together.

That is a “least bad” solution because:

- if several specific variables load, they give more nuanced interpretability;
- if only one or no specific variables load, the summary may preserve broader information that would otherwise disappear;
- the model avoids duplicating the same linguistic signal.

So the original logic is not merely technical; it is a methodological safeguard against redundancy.

## Where your case differs

Your tagset has summary variables that overlap across conceptual domains. For example:

| variable                         | belongs to                                                             |
|----------------------------------|------------------------------------------------------------------------|
| `v150`                           | `v914` infinitive clauses and `v918` non-finite verb forms             |
| `v167-v181`                      | `v913` `que` complement clauses and `v915` positioning/complementation |
| `v012-v013`                      | `v901` pronouns and `v919` PB variable phenomena                       |
| `v065`                           | `v904` verbs and `v916` modals                                         |
| `v112`, `v114-v117`, `v120-v124` | `v905` adverbs and `v917` stance/degree adverbs                        |

This means there is not always a clean one-parent hierarchy:

```plain text
summary → specific variables
```


Instead, some variables have multiple parents:

```plain text
specific variable → summary A and summary B
```


That complicates the binary rule.

## Is overlap itself harmful?

Overlap among **summary definitions** is not necessarily harmful if summaries are treated as metadata or interpretation aids.

But overlap becomes harmful if, in the same factor analysis, you allow:

1. overlapping summary variables to coexist with each other;
2. summary variables to coexist with their components;
3. overlapping components to be inconsistently retained or dropped depending on processing order.

### Example: `v913` and `v915`

- `v913` = all `que` complement clauses;
- `v915` = positioning / stance / complement clauses;
- `v167-v181` are shared by both.

If both `v913` and `v915` remain in the model, they may be highly correlated because they share most of their content. That can produce a factor that reflects the overlap structure rather than textual variation.

So the conservative rule we discussed helps, but it does not solve everything if **two overlapping summary variables are both retained**.

## The key methodological question

There are actually two related but distinct problems:

### Problem A: summary vs specific coexistence

Example:

```plain text
v913 and v167
```


This should generally be avoided.

### Problem B: summary vs summary overlap

Example:

```plain text
v913 and v915
```


This can also be harmful, because both summaries partially measure the same thing.

The previous conservative rule mainly addresses **Problem A**. It prevents a summary from deleting a shared specific variable unless all parent summaries agree.

But we should also think about **Problem B**: should overlapping summaries be allowed to coexist?

## My view

I would be cautious about including overlapping summaries together in the final factor analysis.

If the goal is traditional MDA, I would favor one of these approaches.

---

# Option 1 — Strict hierarchy: no summaries in factor extraction

This is the cleanest statistically.

You already did this in the first unrotated factor analysis by dropping `v900-v919`.

Under this approach:

- factor extraction uses only specific variables;
- summary variables are never reintroduced into the factor analysis;
- summaries can be used later as descriptive or interpretive variables, but not as factor variables.

Advantages:

- no summary/component redundancy;
- no summary/summary overlap;
- cleaner factor interpretation;
- simpler code;
- less risk of artificial correlations.

Disadvantages:

- if a family of specific variables is sparse, its broader signal may disappear;
- you lose the “backup” function of summary variables.

For your project, this is probably the safest from a factor-analytic perspective.

---

# Option 2 — Binary summary check, but with no summary-summary overlap allowed

This follows the older “least worse” logic but adapts it to your overlapping taxonomy.

The rule would be:

1. Drop all summaries initially.
2. Run preliminary factor analysis on specific variables.
3. For each summary, decide whether the summary is needed.
4. If a summary is kept, drop its specific components.
5. But if two summaries overlap and both are candidates for retention, choose only one.

This requires a hierarchy of priority among overlapping summaries.

For example:

| overlap          | possible priority choice                                            |
|------------------|---------------------------------------------------------------------|
| `v904` vs `v916` | keep `v916` if interested in modality; otherwise `v904`             |
| `v905` vs `v917` | keep `v917` if interested in stance/degree; otherwise `v905`        |
| `v913` vs `v915` | choose very carefully; these overlap heavily                        |
| `v914` vs `v918` | keep `v918` for morphology/non-finiteness or `v914` for clause type |

Advantages:

- preserves broad variables where specifics do not load;
- avoids most redundancy.

Disadvantages:

- requires subjective priority decisions;
- more complex and less transparent;
- decisions can affect final factor structure.

---

# Option 3 — Use summaries only as candidates if none of their overlapping sibling summaries are retained

This is stricter than the conservative rule.

Example:

- `v913` and `v915` overlap heavily.
- If both qualify for retention, retain only the more theoretically relevant one.
- If one qualifies and the other does not, retain the qualifying one.
- If neither qualifies, keep specific variables if they loaded.

This is probably the best compromise if you want to preserve the original summary-checking logic.

---

## My recommendation

For your study, I would recommend **not reintroducing summary variables into the factor extraction at all**, at least for the main analysis.

That means:

```plain text
Main TMDA model = specific variables only
```


Then you can run a secondary/sensitivity analysis with summary-variable checking if needed.

Why? Because your tagset is semantically richer and more overlapping than the old Biber-style feature set. The overlap is not accidental; it reflects cross-classification:

- syntactic form,
- semantic function,
- discourse function,
- variation/informality,
- stance,
- clause type.

That is linguistically interesting, but statistically dangerous if represented through both summaries and components in the same correlation matrix.

So I would separate them:

| use                      | variables                                          |
|--------------------------|----------------------------------------------------|
| main factor extraction   | `v001-v230`, excluding `v900-v919`                 |
| interpretation/reporting | summary variables `v900-v919`                      |
| robustness check         | optional model with carefully controlled summaries |

## What I would tell Professor Tony

I would say something like:

> We agree with the principle that summary variables should not coexist with their specific component variables in factor extraction. In the adapted Portuguese tagset, however, some specific variables are members of more than one summary category. Therefore, the simple binary summary/component rule from the earlier implementation becomes order-sensitive and can produce inconsistent exclusions. To avoid artificial covariance and over-weighting, our primary TMDA model will exclude all summary variables from factor extraction. Summary variables will be retained only for descriptive interpretation or tested in a separate sensitivity analysis with explicit overlap controls.

That is methodologically defensible.

## Practical implication for your script

If you accept this recommendation, then the whole “Checking summary variables” block may not be necessary.

Your pipeline would be:

1. Import all DFM variables.
2. Create `&project._no_sum_v` by dropping `v900-v919`.
3. Run unrotated factor analysis on `&project._no_sum_v`.
4. Drop low-communality variables.
5. Run rotated factor analysis on the remaining specific variables.
6. Interpret factors from specific variables only.
7. Optionally use summaries descriptively after factor scoring, but not in extraction.

In that case, you do **not** need to reconstruct `v900-v919` later.

## Bottom line

I think overlap could be harmful if summary variables are included in the factor model, because it can introduce artificial covariance and overrepresent particular linguistic domains.

The least risky solution is:

> **Do not include summary variables in the factor extraction. Drop `v900-v919` and keep them out of the TMDA model.**

If you want continuity with the previous Biber-style pipeline, we can still implement the binary summary-checking mechanism, but I would treat that as a **secondary analysis**, not the main one.

> **User:** I agree with you! I would not take any risks at this moment and let any risky decision-making for when I get a chance to talk to Professor Tony. But just I wonder why Biber chose that weighted compromise model - what would be the benefit? Did he envision a less complex linguistic model at that time? I know that stance language features were introduced later on, and perhaps the consequences of overlapping were overlooked. What do you know about this?

Yes — your interpretation is very plausible. I would frame it less as “Biber overlooked overlap” and more as: **the original MDA feature ecology was designed around a different, more constrained set of grammatical categories, and the summary-variable compromise was a practical solution for sparse, low-frequency linguistic features in factor analysis.**

## Why include summary variables at all?

The benefit of summary variables is mainly **statistical recoverability**.

In MDA, many linguistically meaningful features are rare. A specific feature may be too sparse or unstable to load reliably on a factor, even though the **broader functional domain** it belongs to is important.

For example, imagine separate variables for:

- possibility modals;
- prediction modals;
- necessity modals.

Individually, each may be too infrequent or too text-dependent. But collectively, “modality” may be a robust dimension of variation. A summary variable such as “all modals” can capture that broader domain.

So the compromise is:

> If several specific variables are strong enough, use the specifics.  
> If the specifics are too weak, use the broader summary variable.

That is a reasonable factor-analytic strategy when:

1. feature frequencies are sparse;
2. sample sizes are limited;
3. the model needs enough stable variables to extract interpretable dimensions;
4. the summary variables are mostly hierarchical and non-overlapping.

## Why not simply use only specific variables?

Because specific variables can be noisy. In corpus-linguistic MDA, some features are theoretically meaningful but occur at low rates. If you rely only on specific features, you may lose an entire functional domain because none of its subfeatures individually reaches the loading threshold.

Suppose these all load weakly:

| variable           | loading |
|--------------------|--------:|
| possibility modals |     .18 |
| necessity modals   |     .21 |
| prediction modals  |     .17 |

But the aggregate “all modals” loads at `.36`.

Then a strict specific-only model would miss modality as a relevant dimension. A summary variable can rescue that broader signal.

That is the “least worse” logic you mentioned.

## Why was this acceptable in the original Biber-style tradition?

Historically, early MDA worked with a carefully selected set of linguistic features that were often:

- surface-identifiable;
- functionally motivated;
- relatively established in grammar descriptions;
- not as densely cross-classified as later stance frameworks.

The original feature set was already complex, but the feature taxonomy was less like a multi-layered ontology and more like a practical battery of grammatical counts.

So many summary variables were probably treated as **backup indicators** rather than as independent theoretical constructs.

That makes the binary rule sensible:

- do not include both summary and specific variables;
- use the summary only when the specific variables do not provide enough factor-loading evidence.

## Did Biber envision a less complex linguistic model?

In a way, yes — or more precisely, the original MDA methodology was not designed around the kind of richly overlapping annotation taxonomy you are now using.

Early MDA was built for register variation using sets of linguistic features such as:

- tense/aspect markers;
- pronouns;
- nominal forms;
- passives;
- subordination;
- prepositional phrases;
- type-token ratio;
- word length.

The analytical aim was to discover **co-occurrence patterns** among features across texts, not to model a fully articulated hierarchy of linguistic categories.

Later work, especially involving stance, evaluation, evidentiality, modality, complement clauses, and interactional features, introduced more cross-cutting categories. A single form can belong to multiple conceptual domains:

| feature                               | possible categories                                         |
|---------------------------------------|-------------------------------------------------------------|
| `that`-complement after a mental verb | complement clause, stance, cognition, epistemic positioning |
| modal verb                            | verb, modal, stance/possibility/obligation                  |
| negation                              | adverb, polarity marker, stance/engagement feature          |
| relative clause                       | subordination, noun modification, syntactic complexity      |
| `se` construction                     | pronoun, passive, impersonal, variation phenomenon          |

That cross-classification is linguistically accurate, but it complicates factor analysis.

## Why overlap becomes more serious in richer tagsets

In a simple hierarchy, this is manageable:

```plain text
all_modals
 ├── possibility_modals
 ├── necessity_modals
 └── prediction_modals
```


You can choose either the parent or the children.

But in a cross-classified model, you may have:

```plain text
v150 orações de infinitivo
 ├── v914 all infinitive clauses
 └── v918 all non-finite verb forms
```


or:

```plain text
v167-v181 que-complement stance clauses
 ├── v913 all que-complement clauses
 └── v915 all stance/positioning clauses
```


Now a binary parent-child choice is not enough, because the same child has two parents.

This means decisions are no longer simply:

```plain text
summary vs its specific variables
```


They become:

```plain text
summary A vs summary B vs shared specific variables
```


That is a much harder modeling decision.

## Were the consequences overlooked?

Possibly in some cases, but I would be cautious saying that.

More likely:

1. **The original system had fewer overlapping summary variables**, or at least fewer theoretically salient overlaps.
2. **The summaries were used pragmatically**, not as a full ontology.
3. **Computational/statistical constraints were different**: preserving enough variables for stable factor extraction was a major concern.
4. **The goal was empirical register differentiation**, not exhaustive linguistic taxonomic representation.
5. Later stance and discourse features made overlap much more visible and consequential.

So the compromise was appropriate for the design conditions of earlier MDA, but it may not transfer cleanly to a richer tagset.

## The benefit of the Biber-style compromise

I would summarize the benefit like this:

> It allowed broad linguistic domains to remain available to the factor analysis when their component variables were too rare or too weak to load individually, while avoiding the worst redundancy by not keeping both the summary and the components.

That is a good idea when the summary variables form mostly clean, non-overlapping families.

## The risk in your current project

Your tagset has multiple levels of classification:

- part of speech;
- semantic subclass;
- syntactic function;
- clause type;
- stance/evidentiality;
- modality;
- variation/informality;
- discourse function.

That means some features are intentionally multi-functional. For example, a `que` complement can simultaneously be:

- a complement clause;
- a stance construction;
- an evidential/positioning device;
- controlled by a cognitive verb, communication verb, adjective, noun, etc.

If you let all those summaries compete inside the same factor extraction, you could get dimensions shaped by the taxonomy itself, not only by textual co-occurrence.

## My recommendation remains

For your main analysis, I think you are making the right choice:

> Drop all summary variables from factor extraction and keep only specific variables.

Then you can tell Professor Tony:

> Because our Portuguese tagset includes cross-classified summary variables, we avoided reintroducing summaries into the primary TMDA model. This prevents artificial covariance caused by summary/component and summary/summary overlap. We retain summaries for descriptive follow-up, but not for extraction.

That is conservative and defensible.

## If you later want to test the compromise

You could run a sensitivity analysis with three models:

| model   | variables included               | purpose                            |
|---------|----------------------------------|------------------------------------|
| Model A | specific variables only          | primary, safest model              |
| Model B | Biber-style binary summary check | compare with inherited methodology |
| Model C | manually curated summaries only  | test selected broader domains      |

Then compare:

- factor interpretability;
- variable loadings;
- factor correlations;
- stability;
- whether the same subcorpus distinctions emerge.

If the results are similar, that strengthens your argument. If they differ, that demonstrates that summary-variable handling materially affects the analysis.

## Bottom line

Biber’s compromise likely served a very practical purpose: **to preserve broad linguistic signals when specific variables were too sparse**, while trying to avoid direct redundancy.

But your tagset is more heavily cross-classified, especially because of stance, clause, modality, and variation categories. In that setting, summary variables are more dangerous inside factor extraction.

So I think your current decision is exactly right:

> **Use summary variables descriptively, but exclude them from the primary TMDA factor extraction until the theoretical treatment of overlaps is explicitly settled.**
