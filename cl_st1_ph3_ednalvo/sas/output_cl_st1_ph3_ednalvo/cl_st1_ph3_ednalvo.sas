/* ==========================================================================
   Traditional Multi-Dimensional Analysis
   ========================================================================== */

/* ==========================================================================
   SECTION 1: ENVIRONMENT SETUP AND MACROS
   ========================================================================== */

%let project = cl_st1_ph3_ednalvo ;
%let myfolder = &project ;
%let sasusername = u63529080 ;
%let whereisit = /home/&sasusername ;  /* Online */

libname gelc "&whereisit/&myfolder";

/* Files will NOT be saved to the folder above unless you put in 'gelc.' before every destination */
/* Otherwise files are going to the work library and not saved to the current folder */
/* This is needed to enable SGPLOT. Otherwise, SAS will throw up an error message */

options fmtsearch=(work library);
options validvarname=any;

/* Extraction & cutoff parameters */
/* NOTE: Section 6 currently contains loading-selection logic hard-coded
   for exactly 9 factors. If &extractfactors changes, revise Section 6. */
%let extractfactors = 4 ;
%let factorvars = f1-f&extractfactors ;
%let minloading = .3 ;
%let communalcutoff = .15 ;


/* ==========================================================================
   SECTION 2: DATA INGESTION
   MAIORES_NOTAS, MENORES_NOTAS, MENORES_NOTAS_GEMINI, MENORES_NOTAS_GPT
   ========================================================================== */

/* --------------------------------------------------------------------------
   Macro to ingest one DFM TSV file.

   Expected TSV structure:
   filename    subcorpus    wcount    v001 ... v006    v007_1-v007_4
   v008-v230    v900-v919

   Notes:
   - filename and subcorpus are character variables.
   - wcount and all v* variables are numeric.
   - DLM='09'x specifies tab-delimited input.
   - FIRSTOBS=2 skips the header row.
   -------------------------------------------------------------------------- */

%macro import_dfm(dataset=, infile=);

DATA &dataset ;
    LENGTH filename $150 subcorpus $50;

    INFILE "&whereisit/&myfolder/&infile"
        DLM='09'x
        DSD
        FIRSTOBS=2
        TRUNCOVER;

    INPUT
        filename :$150.
        subcorpus :$50.
        wcount
        v001-v006
        v007_1-v007_4
        v008-v230
        v900-v919
    ;
RUN;

%mend import_dfm;


/* 1A: Ingest maiores_notas subcorpus */
%import_dfm(
    dataset=corp_maiores_notas,
    infile=maiores_notas_counts.tsv
);


/* 1B: Ingest menores_notas subcorpus */
%import_dfm(
    dataset=corp_menores_notas,
    infile=menores_notas_counts.tsv
);


/* 1C: Ingest menores_notas_gemini subcorpus */
%import_dfm(
    dataset=corp_menores_notas_gemini,
    infile=menores_notas_gemini_counts.tsv
);


/* 1D: Ingest menores_notas_gpt subcorpus */
%import_dfm(
    dataset=corp_menores_notas_gpt,
    infile=menores_notas_gpt_counts.tsv
);


/* ==========================================================================
   SECTION 3: BASE CORPUS PREPARATION & INITIAL EXPORTS
   ========================================================================== */

/* Combine all four subcorpora for Traditional MDA */
DATA base_corpus;
    LENGTH filename $150 subcorpus $50;

    SET
        corp_maiores_notas
        corp_menores_notas
        corp_menores_notas_gemini
        corp_menores_notas_gpt
    ;
RUN;


/* Set up the project dataset used throughout the TMDA pipeline */
DATA &project;
    SET base_corpus;
RUN;


/* Quick visual check of filenames */
ODS EXCLUDE NONE;
PROC PRINT DATA=&project (FIRSTOBS=1 OBS=20);
    VAR filename subcorpus;
RUN;


/* Export initial combined dataset */
PROC EXPORT
    DATA=WORK.&project
    DBMS=CSV
    OUTFILE="&whereisit/&myfolder/&project..csv"
    REPLACE;
RUN;


/* --------------------------------------------------------------------------
   Summary-variable and metadata-variable handling

   The 9xx variables are aggregate/summary variables derived from specific
   variables in the tagset. In traditional MDA/factor analysis, allowing a
   summary variable to coexist with the specific variables from which it is
   computed can introduce artificial covariance, overweight a linguistic domain,
   and complicate interpretation.

   The variable wcount is retained in the full project dataset for descriptive
   corpus-size reporting, but it is excluded from factor extraction because it is
   document metadata rather than a linguistic feature count to be interpreted as
   a factor-loading variable.

   Therefore, for the primary TMDA model, wcount and all summary variables
   v900-v919 are excluded from factor extraction.
   -------------------------------------------------------------------------- */

DATA &project._no_sum_v (
    DROP = wcount v900-v919
);
    SET &project;
RUN;


/* --------------------------------------------------------------------------
   Remove zero-variance variables before factor analysis.

   PROC FACTOR requires a usable, non-singular correlation matrix. Variables with
   zero variance cannot be correlated meaningfully and may cause PROC FACTOR to
   stop with a singular-correlation-matrix error.

   These variables are removed before the unrotated analysis and before the
   communality cutoff is applied.
   -------------------------------------------------------------------------- */

ODS EXCLUDE ALL;

PROC MEANS DATA=&project._no_sum_v NOPRINT;
    VAR _NUMERIC_;
    OUTPUT OUT=variance_check(DROP=_TYPE_ _FREQ_) STD=;
RUN;

ODS EXCLUDE NONE;

PROC TRANSPOSE DATA=variance_check OUT=variance_check_t;
RUN;

%let zerovar=;

PROC SQL NOPRINT;
    SELECT _NAME_ INTO :zerovar SEPARATED BY ' '
    FROM variance_check_t
    WHERE COL1 = 0 OR MISSING(COL1);
QUIT;

%put NOTE: Zero-variance variables to be dropped before factor analysis: &zerovar.;

%macro drop_zero_variance_vars;

    %if %superq(zerovar) ne %then %do;

        DATA &project._factor_input;
            SET &project._no_sum_v;
            DROP &zerovar;
        RUN;

    %end;
    %else %do;

        DATA &project._factor_input;
            SET &project._no_sum_v;
        RUN;

        %put NOTE: No zero-variance variables found.;

    %end;

%mend drop_zero_variance_vars;

%drop_zero_variance_vars;


/* Save zero-variance variables dropped before factor analysis */
DATA zero_variance_dropped;
    SET variance_check_t;
    IF COL1 = 0 OR MISSING(COL1);
RUN;

ODS EXCLUDE NONE;
PROC EXPORT
    DATA=WORK.zero_variance_dropped
    DBMS=CSV
    OUTFILE="&whereisit/&myfolder/zero_variance_dropped.csv"
    REPLACE;
RUN;
ODS EXCLUDE ALL;


/* ==========================================================================
   SECTION 4: UNROTATED FACTOR ANALYSIS & COMMUNALITY CUTOFF
   ========================================================================== */

/* Unrotated Factor Analysis without metadata, summary, or zero-variance
   variables, before dropping low-communality variables.

   The input dataset &project._factor_input excludes wcount, all 9xx summary
   variables (v900-v919), and any zero-variance variables detected above. */
OPTIONS VALIDVARNAME=ANY;

ODS EXCLUDE NONE;
ods html file="&whereisit/&myfolder/unrotated.html";
ods trace on;

proc factor
OUTSTAT=fout
data=&project._factor_input
method=principal scree
mineigen=0
nfactors=100
priors=smc
heywood;
var
_NUMERIC_ ;
run;
quit;

ods trace off;
ods html close;
ODS EXCLUDE ALL;


/*** Find low communalities ***/

data fout2;
    set fout (where=(_TYPE_="COMMUNAL"));
run;

proc transpose data=fout2 out=communal;
    id _TYPE_;
run;

/* Identify variables with communality below the cutoff.

   Robustness note:
   &names is explicitly initialized before PROC SQL. If no variables fall below
   the cutoff, &names remains empty. The macro below then creates
   &project._no_low_c without issuing an empty DROP statement. */
%let names=;

proc sql noprint;
    select _name_ into :names separated by ' '
    from communal
    where communal < &communalcutoff ;
quit;


/* Drop low-communality variables only when such variables exist. */
%macro drop_low_communality_vars;

    %if %superq(names) ne %then %do;

        data &project._no_low_c ;
            set &project._factor_input ;
            drop &names;
        run;

    %end;
    %else %do;

        data &project._no_low_c ;
            set &project._factor_input ;
        run;

        %put NOTE: No variables had communalities below &communalcutoff..;
        %put NOTE: Dataset &project._no_low_c created without dropping variables.;

    %end;

%mend drop_low_communality_vars;

%drop_low_communality_vars;


/* Save variables dropped because of low communality */
PROC SORT DATA=communal;
    BY _NAME_;
RUN;

data communal_dropped ;
    set communal ;
    if COMMUNAL < &communalcutoff ;
RUN;

ODS EXCLUDE NONE;
PROC EXPORT
  DATA=WORK.communal_dropped
  DBMS=CSV
  OUTFILE="&whereisit/&myfolder/communalities_dropped.csv"
  REPLACE;
RUN;
ODS EXCLUDE ALL;


/* Scree plot */
data fout2;
  set fout (where=(_TYPE_="EIGENVAL"));
run;

proc transpose data=fout2 out=fout3 (drop=_NAME_);
    id _TYPE_;
run;

data fout4 ;
    set fout3 ;
    factor = _n_;
    if factor <= 20 ;
run;

ODS EXCLUDE NONE;
ods listing gpath="&whereisit/&myfolder/";
ods graphics / imagename="scree" imagefmt=png;

title "Scree plot";
proc sgplot data=fout4 ;
    series x=factor y=EIGENVAL / datalabel=factor;
run;
title;

ODS EXCLUDE ALL;


/* ==========================================================================
   SECTION 5: INITIAL ROTATED FACTOR ANALYSIS & VAR SELECTION PLACEHOLDER
   ========================================================================== */

/* --------------------------------------------------------------------------
   Preliminary rotated factor analysis.

   This diagnostic rotated analysis uses the low-communality-filtered,
   summary-free, zero-variance-filtered dataset: &project._no_low_c.

   Because rotate=promax requests an oblique rotation, the rotated factor
   pattern is read from _TYPE_="PATTERN".
   -------------------------------------------------------------------------- */

ODS EXCLUDE ALL;
OPTIONS VALIDVARNAME=ANY;

proc factor
OUTSTAT = rotated
data=&project._no_low_c
method=principal
scree
msa
mineigen=0
priors=smc
nfactors= &extractfactors
rotate=promax
heywood;
var
_NUMERIC_ ;
run;
quit;
ods html close;


/* Preserve the preliminary rotated pattern for possible inspection or future
   variable-selection logic. */
OPTIONS VALIDVARNAME=ANY;

data rotated1;
  set rotated (where=(_TYPE_="PATTERN"));
run;

proc transpose data=rotated1 out=rotated2 ;
id _NAME_ ;
run;


/* --------------------------------------------------------------------------
   Variable-selection placeholder.

   For the current primary TMDA model, this step intentionally performs no
   additional selection beyond:
   1. removing metadata variable wcount;
   2. removing summary variables v900-v919;
   3. removing zero-variance variables; and
   4. removing variables below the communality cutoff.

   The dataset name &project._sum_check is retained because later sections of
   the original TMDA pipeline refer to it.
   -------------------------------------------------------------------------- */

data &project._sum_check ;
    set &project._no_low_c ;
run;


/* ==========================================================================
   SECTION 6: FINAL ROTATED FACTOR ANALYSIS & LOADINGS TABLE
   ========================================================================== */

ODS EXCLUDE NONE;
ods html file="&whereisit/&myfolder/rotated.html";
ods trace on;

proc factor
OUTSTAT = rotatedfinal
data=&project._sum_check
method=principal
scree
msa
mineigen=0
priors=smc
nfactors= &extractfactors
rotate=promax
heywood;
var
_NUMERIC_ ;
run;
quit;

ods trace off;
ods html close;
ODS EXCLUDE ALL;


/* Reformat OUTSTAT to obtain the promax-rotated factor pattern.

   Because rotate=promax is oblique, interpretation and scoring are based on
   _TYPE_="PATTERN", not _TYPE_="PREROTAT". */
OPTIONS VALIDVARNAME=ANY;

data rotated2;
  set rotatedfinal (where=(_TYPE_="PATTERN"));
run;

proc transpose data=rotated2 out=rotated2 ;
id _NAME_ ;
run;


/* Identify the primary loading for each variable.

   NOTE: This block is intentionally hard-coded for nine factors. */
OPTIONS VALIDVARNAME=ANY;

data rotated3;
   set rotated2;
      loaded = 0 ;

        if     abs(factor1) > abs(factor2)
           AND abs(factor1) > abs(factor3)
           AND abs(factor1) > abs(factor4)
           AND abs(factor1) > abs(factor5)
           AND abs(factor1) > abs(factor6)
           AND abs(factor1) > abs(factor7)
           AND abs(factor1) > abs(factor8)
           AND abs(factor1) > abs(factor9)
           AND factor1 > 0 AND abs(factor1) >= &minloading then do; factor = 'f1'; pole = 1;  loaded = 1; end ;

   else if     abs(factor2) > abs(factor1)
           AND abs(factor2) > abs(factor3)
           AND abs(factor2) > abs(factor4)
           AND abs(factor2) > abs(factor5)
           AND abs(factor2) > abs(factor6)
           AND abs(factor2) > abs(factor7)
           AND abs(factor2) > abs(factor8)
           AND abs(factor2) > abs(factor9)
           AND factor2 > 0 AND abs(factor2) >= &minloading then do; factor = 'f2'; pole = 1;  loaded = 1; end ;

   else if     abs(factor3) > abs(factor1)
           AND abs(factor3) > abs(factor2)
           AND abs(factor3) > abs(factor4)
           AND abs(factor3) > abs(factor5)
           AND abs(factor3) > abs(factor6)
           AND abs(factor3) > abs(factor7)
           AND abs(factor3) > abs(factor8)
           AND abs(factor3) > abs(factor9)
           AND factor3 > 0 AND abs(factor3) >= &minloading then do; factor = 'f3'; pole = 1;  loaded = 1; end ;

   else if     abs(factor4) > abs(factor1)
           AND abs(factor4) > abs(factor2)
           AND abs(factor4) > abs(factor3)
           AND abs(factor4) > abs(factor5)
           AND abs(factor4) > abs(factor6)
           AND abs(factor4) > abs(factor7)
           AND abs(factor4) > abs(factor8)
           AND abs(factor4) > abs(factor9)
           AND factor4 > 0 AND abs(factor4) >= &minloading then do; factor = 'f4'; pole = 1;  loaded = 1; end ;

   else if     abs(factor5) > abs(factor1)
           AND abs(factor5) > abs(factor2)
           AND abs(factor5) > abs(factor3)
           AND abs(factor5) > abs(factor4)
           AND abs(factor5) > abs(factor6)
           AND abs(factor5) > abs(factor7)
           AND abs(factor5) > abs(factor8)
           AND abs(factor5) > abs(factor9)
           AND factor5 > 0 AND abs(factor5) >= &minloading then do; factor = 'f5'; pole = 1;  loaded = 1; end ;

   else if     abs(factor6) > abs(factor1)
           AND abs(factor6) > abs(factor2)
           AND abs(factor6) > abs(factor3)
           AND abs(factor6) > abs(factor4)
           AND abs(factor6) > abs(factor5)
           AND abs(factor6) > abs(factor7)
           AND abs(factor6) > abs(factor8)
           AND abs(factor6) > abs(factor9)
           AND factor6 > 0 AND abs(factor6) >= &minloading then do; factor = 'f6'; pole = 1;  loaded = 1; end ;

   else if     abs(factor7) > abs(factor1)
           AND abs(factor7) > abs(factor2)
           AND abs(factor7) > abs(factor3)
           AND abs(factor7) > abs(factor4)
           AND abs(factor7) > abs(factor5)
           AND abs(factor7) > abs(factor6)
           AND abs(factor7) > abs(factor8)
           AND abs(factor7) > abs(factor9)
           AND factor7 > 0 AND abs(factor7) >= &minloading then do; factor = 'f7'; pole = 1;  loaded = 1; end ;

   else if     abs(factor8) > abs(factor1)
           AND abs(factor8) > abs(factor2)
           AND abs(factor8) > abs(factor3)
           AND abs(factor8) > abs(factor4)
           AND abs(factor8) > abs(factor5)
           AND abs(factor8) > abs(factor6)
           AND abs(factor8) > abs(factor7)
           AND abs(factor8) > abs(factor9)
           AND factor8 > 0 AND abs(factor8) >= &minloading then do; factor = 'f8'; pole = 1;  loaded = 1; end ;

   else if     abs(factor9) > abs(factor1)
           AND abs(factor9) > abs(factor2)
           AND abs(factor9) > abs(factor3)
           AND abs(factor9) > abs(factor4)
           AND abs(factor9) > abs(factor5)
           AND abs(factor9) > abs(factor6)
           AND abs(factor9) > abs(factor7)
           AND abs(factor9) > abs(factor8)
           AND factor9 > 0 AND abs(factor9) >= &minloading then do; factor = 'f9'; pole = 1;  loaded = 1; end ;

  else  if     abs(factor1) > abs(factor2)
           AND abs(factor1) > abs(factor3)
           AND abs(factor1) > abs(factor4)
           AND abs(factor1) > abs(factor5)
           AND abs(factor1) > abs(factor6)
           AND abs(factor1) > abs(factor7)
           AND abs(factor1) > abs(factor8)
           AND abs(factor1) > abs(factor9)
           AND factor1 < 0 AND abs(factor1) >= &minloading then do; factor = 'f1'; pole = -1;  loaded = 1; end ;

   else if     abs(factor2) > abs(factor1)
           AND abs(factor2) > abs(factor3)
           AND abs(factor2) > abs(factor4)
           AND abs(factor2) > abs(factor5)
           AND abs(factor2) > abs(factor6)
           AND abs(factor2) > abs(factor7)
           AND abs(factor2) > abs(factor8)
           AND abs(factor2) > abs(factor9)
           AND factor2 < 0 AND abs(factor2) >= &minloading then do; factor = 'f2'; pole = -1;  loaded = 1; end ;

   else if     abs(factor3) > abs(factor1)
           AND abs(factor3) > abs(factor2)
           AND abs(factor3) > abs(factor4)
           AND abs(factor3) > abs(factor5)
           AND abs(factor3) > abs(factor6)
           AND abs(factor3) > abs(factor7)
           AND abs(factor3) > abs(factor8)
           AND abs(factor3) > abs(factor9)
           AND factor3 < 0 AND abs(factor3) >= &minloading then do; factor = 'f3'; pole = -1;  loaded = 1; end ;

   else if     abs(factor4) > abs(factor1)
           AND abs(factor4) > abs(factor2)
           AND abs(factor4) > abs(factor3)
           AND abs(factor4) > abs(factor5)
           AND abs(factor4) > abs(factor6)
           AND abs(factor4) > abs(factor7)
           AND abs(factor4) > abs(factor8)
           AND abs(factor4) > abs(factor9)
           AND factor4 < 0 AND abs(factor4) >= &minloading then do; factor = 'f4'; pole = -1;  loaded = 1; end ;

   else if     abs(factor5) > abs(factor1)
           AND abs(factor5) > abs(factor2)
           AND abs(factor5) > abs(factor3)
           AND abs(factor5) > abs(factor4)
           AND abs(factor5) > abs(factor6)
           AND abs(factor5) > abs(factor7)
           AND abs(factor5) > abs(factor8)
           AND abs(factor5) > abs(factor9)
           AND factor5 < 0 AND abs(factor5) >= &minloading then do; factor = 'f5'; pole = -1;  loaded = 1; end ;

   else if     abs(factor6) > abs(factor1)
           AND abs(factor6) > abs(factor2)
           AND abs(factor6) > abs(factor3)
           AND abs(factor6) > abs(factor4)
           AND abs(factor6) > abs(factor5)
           AND abs(factor6) > abs(factor7)
           AND abs(factor6) > abs(factor8)
           AND abs(factor6) > abs(factor9)
           AND factor6 < 0 AND abs(factor6) >= &minloading then do; factor = 'f6'; pole = -1;  loaded = 1; end ;

   else if     abs(factor7) > abs(factor1)
           AND abs(factor7) > abs(factor2)
           AND abs(factor7) > abs(factor3)
           AND abs(factor7) > abs(factor4)
           AND abs(factor7) > abs(factor5)
           AND abs(factor7) > abs(factor6)
           AND abs(factor7) > abs(factor8)
           AND abs(factor7) > abs(factor9)
           AND factor7 < 0 AND abs(factor7) >= &minloading then do; factor = 'f7'; pole = -1;  loaded = 1; end ;

   else if     abs(factor8) > abs(factor1)
           AND abs(factor8) > abs(factor2)
           AND abs(factor8) > abs(factor3)
           AND abs(factor8) > abs(factor4)
           AND abs(factor8) > abs(factor5)
           AND abs(factor8) > abs(factor6)
           AND abs(factor8) > abs(factor7)
           AND abs(factor8) > abs(factor9)
           AND factor8 < 0 AND abs(factor8) >= &minloading then do; factor = 'f8'; pole = -1;  loaded = 1; end ;

   else if     abs(factor9) > abs(factor1)
           AND abs(factor9) > abs(factor2)
           AND abs(factor9) > abs(factor3)
           AND abs(factor9) > abs(factor4)
           AND abs(factor9) > abs(factor5)
           AND abs(factor9) > abs(factor6)
           AND abs(factor9) > abs(factor7)
           AND abs(factor9) > abs(factor8)
           AND factor9 < 0 AND abs(factor9) >= &minloading then do; factor = 'f9'; pole = -1;  loaded = 1; end ;
run;

data rotated4 ;
    set rotated3 ;
    if loaded = 1;
run;
quit;


/* ==========================================================================
   SECTION 6A: FEATURE LABELS
   ========================================================================== */

PROC FORMAT library=work ;
  VALUE $featurelabels

  /* A. Artigos e determinantes */
  "v001" = "Artigos definidos"
  "v002" = "Artigos indefinidos"
  "v003" = "Contrações de preposição + artigo"
  "v004" = "Determinantes demonstrativos"
  "v005" = "Determinantes possessivos"
  "v006" = "Determinantes indefinidos"
  "v007_1" = "Determinantes numerais cardinais"
  "v007_2" = "Determinantes numerais ordinais"
  "v007_3" = "Determinantes numerais multiplicativos"
  "v007_4" = "Determinantes numerais partitivos ou fracionários"
  "v008" = "Determinantes interrogativos e exclamativos"

  /* B. Pronomes */
  "v009" = "Pronomes pessoais retos"
  "v010" = "Pronomes pessoais oblíquos átonos"
  "v011" = "Pronomes pessoais oblíquos tônicos"
  "v012" = "Pronomes de objeto direto"
  "v013" = "Pronomes de objeto indireto"
  "v014" = "Pronomes reflexivos"
  "v015" = "Pronomes possessivos"
  "v016" = "Pronomes demonstrativos"
  "v017" = "Pronomes indefinidos"
  "v018" = "Pronomes relativos"
  "v019" = "Pronomes interrogativos e exclamativos"
  "v020" = "Formas pronominais neutras"
  "v021" = "Pronomes relativos precedidos de preposição"
  "v022" = "Quantificadores pronominais ou determinativos"
  "v023" = "Pronomes pessoais em posição de sujeito"
  "v024" = "Pronomes de primeira pessoa em posição de sujeito"
  "v025" = "Pronomes de segunda pessoa em posição de sujeito"
  "v026" = "Pronomes de terceira pessoa em posição de sujeito"

  /* C. Substantivos */
  "v027" = "Substantivos próprios"
  "v028" = "Substantivos comuns"
  "v029" = "Substantivos abstratos"
  "v030" = "Substantivos concretos"
  "v031" = "Substantivos animados"
  "v032" = "Substantivos coletivos"
  "v033" = "Substantivos de quantidade"
  "v034" = "Substantivos cognitivos"
  "v035" = "Substantivos de processo"
  "v036" = "Substantivos técnicos"
  "v037" = "Nominalizações"
  "v038" = "Substantivos de lugar"
  "v039" = "Substantivos institucionais"
  "v040" = "Substantivos em posição de sujeito"
  "v041" = "Nominalizações em posição de sujeito"

  /* D. Adjetivos */
  "v042" = "Adjetivos qualificativos atributivos"
  "v043" = "Adjetivos qualificativos predicativos"
  "v044" = "Adjetivos relacionais"
  "v045" = "Adjetivos avaliativos"
  "v046" = "Adjetivos de tamanho"
  "v047" = "Adjetivos de idade e tempo"
  "v048" = "Adjetivos de cor"
  "v049" = "Adjetivos de nacionalidade e origem"
  "v050" = "Adjetivos atributivos pré-nominais"
  "v051" = "Adjetivos atributivos pós-nominais"
  "v052" = "Adjetivos superlativos"
  "v053" = "Adjetivos tópicos ou temáticos"
  "v054" = "Adjetivos exceto avaliativos"

  /* E. Verbos */
  "v055" = "Verbos lexicais"
  "v056" = "Verbos auxiliares"
  "v057" = "Verbos copulativos"
  "v058" = "Verbos de comunicação"
  "v059" = "Verbos cognitivos/mentais"
  "v060" = "Verbos de percepção"
  "v061" = "Verbos de movimento"
  "v062" = "Verbos causativos"
  "v063" = "Verbos existenciais"
  "v064" = "Verbos aspectuais"
  "v065" = "Verbos modais e semimodais"
  "v066" = "Verbos de ação/atividade"
  "v067" = "Verbos de ocorrência"
  "v068" = "Verbos de facilitação"
  "v069" = "Verbos privados"
  "v070" = "Verbos públicos"
  "v071" = "Verbos persuasivos/suasivos"
  "v072" = "Verbos de desejo/volição"
  "v073" = "Verbos de probabilidade/aparência"
  "v074" = "Modais de possibilidade"
  "v075" = "Modais de obrigação"
  "v076" = "Modais de necessidade"
  "v077" = "Modais de capacidade"
  "v078" = "Modais de evidencialidade/aparência"

  /* F. Tempos, aspectos, modos e voz verbal */
  "v079" = "Presente do indicativo"
  "v080" = "Pretérito perfeito simples"
  "v081" = "Pretérito imperfeito"
  "v082" = "Pretérito mais-que-perfeito simples e composto"
  "v083" = "Futuro do presente"
  "v084" = "Futuro perifrástico"
  "v085" = "Futuro do pretérito/condicional"
  "v086" = "Imperativo afirmativo"
  "v087" = "Imperativo negativo"
  "v088" = "Presente do subjuntivo"
  "v089" = "Pretérito imperfeito do subjuntivo"
  "v090" = "Futuro do subjuntivo"
  "v091" = "Aspecto perfeito composto"
  "v092" = "Perífrases progressivas"
  "v093" = "Perífrases incoativas"
  "v094" = "Perífrases terminativas"
  "v095" = "Voz passiva analítica"
  "v096" = "Voz passiva sintética/pronominal"
  "v097" = "Construções impessoais"
  "v098" = "Verbo no infinitivo"
  "v099" = "Infinitivo pessoal"
  "v100" = "Verbo no gerúndio"
  "v101" = "Particípio passado"
  "v102" = "Modo indicativo"
  "v103" = "Passiva analítica com agente"
  "v104" = "Passiva analítica sem agente"
  "v105" = "Auxiliares com clivagem por advérbio"

  /* G. Advérbios */
  "v106" = "Advérbios de tempo"
  "v107" = "Advérbios de lugar"
  "v108" = "Advérbios de modo"
  "v109" = "Advérbios de quantidade/intensidade"
  "v110" = "Advérbios de afirmação"
  "v111" = "Advérbios de negação"
  "v112" = "Advérbios de dúvida/probabilidade"
  "v113" = "Advérbios focalizadores"
  "v114" = "Advérbios intensificadores/amplificadores"
  "v115" = "Advérbios atitudinais"
  "v116" = "Advérbios epistêmicos/factivos"
  "v117" = "Advérbios de mitigação/hedges"
  "v118" = "Advérbio de negação não"
  "v119" = "Advérbios negativos exceto não"
  "v120" = "Advérbios de probabilidade"
  "v121" = "Advérbios factivos/de certeza"
  "v122" = "Advérbios não factuais/evidenciais"
  "v123" = "Advérbios suavizadores/downtoners"
  "v124" = "Advérbios enfatizadores"
  "v125" = "Advérbios comparativos"
  "v126" = "Advérbios compostos ou locuções adverbiais"

  /* H. Preposições */
  "v127" = "Todas as preposições simples"
  "v128" = "Locuções prepositivas"
  "v129" = "Contrações preposicionais"
  "v130" = "Regência/preposição não padrão ou variável"

  /* I. Conjunções e subordinação */
  "v131" = "Conjunções coordenativas aditivas"
  "v132" = "Conjunções coordenativas alternativas"
  "v133" = "Conjunções coordenativas adversativas"
  "v134" = "Conjunções subordinativas causais"
  "v135" = "Conjunções subordinativas condicionais"
  "v136" = "Conjunções subordinativas concessivas"
  "v137" = "Conjunções subordinativas temporais"
  "v138" = "Conjunções subordinativas consecutivas"
  "v139" = "Conjunções subordinativas finais"
  "v140" = "Conjunções subordinativas comparativas"
  "v141" = "Conjunções subordinativas integrantes"
  "v142" = "Conjunções coordenativas conclusivas"
  "v143" = "Coordenação frasal"
  "v144" = "Coordenação oracional"
  "v145" = "Conjunções subordinativas conformativas"
  "v146" = "Conjunções subordinativas proporcionais"

  /* J. Orações e estruturas sintáticas */
  "v147" = "Orações relativas"
  "v148" = "Orações completivas com que"
  "v149" = "Orações interrogativas indiretas"
  "v150" = "Orações de infinitivo"
  "v151" = "Orações de gerúndio"
  "v152" = "Orações de particípio"
  "v153" = "Orações sem verbo/elípticas"
  "v154" = "Elipse de sujeito/pro-drop"
  "v155" = "Elipse de outros constituintes"
  "v156" = "Construções com se"
  "v157" = "Construções de tópico-comentário/deslocamento à esquerda"
  "v158" = "Construções relativas resumptivas"
  "v159" = "Ordem não canônica de constituintes"
  "v160" = "Interrogativas diretas com elemento interrogativo"
  "v161" = "Interrogativas diretas sem elemento interrogativo/polares"
  "v162" = "Orações relativas com lacuna de sujeito"
  "v163" = "Orações relativas com lacuna de objeto"
  "v164" = "Orações relativas com preposição deslocada ou omitida"
  "v165" = "Orações reduzidas de particípio pós-nominais"
  "v166" = "Apagamento de que em completivas"

  /* K. Orações de posicionamento, complementação e controle oracional */
  "v167" = "Completivas com que controladas por verbo dicendi/comunicação"
  "v168" = "Completivas com que controladas por verbo cognitivo/mental"
  "v169" = "Completivas com que controladas por verbo de desejo/volição"
  "v170" = "Completivas com que controladas por verbo de probabilidade/aparência"
  "v171" = "Completivas com que controladas por adjetivo avaliativo"
  "v172" = "Completivas com que controladas por adjetivo de certeza"
  "v173" = "Completivas com que controladas por adjetivo de probabilidade"
  "v174" = "Completivas com que controladas por substantivo factual"
  "v175" = "Completivas com que controladas por substantivo não factual"
  "v176" = "Completivas com que controladas por substantivo de atitude"
  "v177" = "Completivas com que controladas por substantivo de probabilidade"
  "v178" = "Completivas com que no indicativo"
  "v179" = "Completivas com que no subjuntivo"
  "v180" = "Completivas com que controladas por advérbio ou expressão adverbial"
  "v181" = "Completivas com que controladas por preposição ou locução prepositiva"
  "v182" = "Infinitivo controlado por verbo de desejo/volição"
  "v183" = "Infinitivo controlado por verbo cognitivo/mental"
  "v184" = "Infinitivo controlado por verbo causativo"
  "v185" = "Infinitivo controlado por verbo modal ou semimodal"
  "v186" = "Infinitivo controlado por verbo de probabilidade/aparência"
  "v187" = "Infinitivo controlado por adjetivo avaliativo"
  "v188" = "Infinitivo controlado por adjetivo de facilidade/dificuldade"
  "v189" = "Infinitivo controlado por adjetivo de certeza/probabilidade"
  "v190" = "Infinitivo controlado por adjetivo atitudinal ou afetivo"
  "v191" = "Infinitivo controlado por substantivo"
  "v192" = "Infinitivo introduzido por preposição"
  "v193" = "Infinitivo controlado por substantivo factual ou não factual"
  "v194" = "Infinitivo controlado por substantivo de atitude"

  /* L. Colocação pronominal e clíticos */
  "v195" = "Próclise"
  "v196" = "Ênclise"
  "v197" = "Mesóclise"
  "v198" = "Próclise em início de frase"
  "v199" = "Alternância entre clítico e pronome pleno"
  "v200" = "Contrações com pronomes clíticos"

  /* M. Marcadores discursivos */
  "v201" = "Marcadores de abertura"
  "v202" = "Marcadores de reformulação"
  "v203" = "Marcadores de consequência"
  "v204" = "Marcadores de acordo/confirmação"
  "v205" = "Marcadores apelativos"
  "v206" = "Marcadores de fechamento"
  "v207" = "Partículas discursivas/conversacionais"

  /* N. Traços conversacionais */
  "v208" = "Interjeições"
  "v209" = "Vocativos"
  "v210" = "Muletilhas"
  "v211" = "Hesitações"
  "v212" = "Repetições"
  "v213" = "Reformulações"
  "v214" = "Risos"
  "v215" = "Sobreposições/interrupções"
  "v216" = "Perguntas de confirmação"

  /* O. Variação, informalidade e português brasileiro digital */
  "v217" = "Formas reduzidas e abreviações comuns"
  "v218" = "Grafias expressivas ou alongadas"
  "v219" = "Gírias e expressões avaliativas"
  "v220" = "Empréstimos e termos de redes sociais"
  "v221" = "Expressões avaliativas recentes"
  "v222" = "Hashtags e marcadores de tópico digital"
  "v223" = "Emojis e emoticons com função discursiva ou avaliativa"
  "v224" = "Sufixos e formações produtivas digitais"
  "v225" = "Alternância de código"
  "v226" = "Marcadores de oralidade em escrita digital"
  "v227" = "Formas não padrão de concordância relevantes para PB"
  "v228" = "Formas não padrão de regência ou complemento verbal"
  "v229" = "Construções de oralidade informal"
  "v230" = "Expressões digitais multimodais ou performativas"

  /* P. Traços derivados/agregados */
  "v900" = "Todos os artigos"
  "v901" = "Todos os pronomes"
  "v902" = "Todos os substantivos"
  "v903" = "Todos os adjetivos"
  "v904" = "Todos os verbos"
  "v905" = "Todos os advérbios"
  "v906" = "Todas as preposições"
  "v907" = "Todas as conjunções"
  "v908" = "Todas as passivas"
  "v909" = "Todas as relativas"
  "v910" = "Todos os marcadores discursivos"
  "v911" = "Todos os traços conversacionais"
  "v912" = "Todos os traços digitais"
  "v913" = "Todas as orações com que"
  "v914" = "Todas as orações de infinitivo"
  "v915" = "Todas as orações de posicionamento"
  "v916" = "Todos os modais"
  "v917" = "Todos os advérbios de posicionamento e grau"
  "v918" = "Todas as formas verbais não finitas"
  "v919" = "Todos os fenômenos variáveis do PB"
  ;
RUN;
QUIT;


/* ==========================================================================
   SECTION 6B: LOADINGS TABLES
   ========================================================================== */

ODS EXCLUDE NONE;
ods html file="&whereisit/&myfolder/loadtable.html";

%macro create_load_tables(howmany);
%do i=1 %to &howmany;

title "LOADINGS TABLE";
title2 "Factor &i pos" ;

data temp;
  set rotated4 ;
  where factor="f&i" and pole=1 ;
run;

proc sort data=temp;
  by descending Factor&i ;
run;

proc print data=temp ;
  FORMAT _NAME_ $featurelabels.;
  var _NAME_ Factor&i ;
run;

title "Factor &i neg" ;

data temp;
  set rotated4 ;
  where factor="f&i" and pole=-1 ;
run;

proc sort data=temp;
  by Factor&i ;
run;

proc print data=temp ;
  FORMAT _NAME_ $featurelabels.;
  var _NAME_ Factor&i ;
run;

%end;
%mend create_load_tables;

%create_load_tables(&extractfactors)

ods html close;
quit;

PROC EXPORT
  DATA= WORK.rotated3
  DBMS=CSV
  OUTFILE="&whereisit/&myfolder/rotated.csv"
  REPLACE;
RUN;


/* All variables that loaded, for interpretation */
OPTIONS VALIDVARNAME=ANY;

data rotatedinterpr (drop = factor pole) ;
   set rotated3;

    if factor1 > 0 AND abs(factor1) >= &minloading then do; secfactor1 = 'f1'; secpolef1 = 1;  end ;
    if factor2 > 0 AND abs(factor2) >= &minloading then do; secfactor2 = 'f2'; secpolef2 = 1;  end ;
    if factor3 > 0 AND abs(factor3) >= &minloading then do; secfactor3 = 'f3'; secpolef3 = 1;  end ;
    if factor4 > 0 AND abs(factor4) >= &minloading then do; secfactor4 = 'f4'; secpolef4 = 1;  end ;
    if factor5 > 0 AND abs(factor5) >= &minloading then do; secfactor5 = 'f5'; secpolef5 = 1;  end ;
    if factor6 > 0 AND abs(factor6) >= &minloading then do; secfactor6 = 'f6'; secpolef6 = 1;  end ;
    if factor7 > 0 AND abs(factor7) >= &minloading then do; secfactor7 = 'f7'; secpolef7 = 1;  end ;
    if factor8 > 0 AND abs(factor8) >= &minloading then do; secfactor8 = 'f8'; secpolef8 = 1;  end ;
    if factor9 > 0 AND abs(factor9) >= &minloading then do; secfactor9 = 'f9'; secpolef9 = 1;  end ;

    if factor1 < 0 AND abs(factor1) >= &minloading then do; secfactor1 = 'f1'; secpolef1 = -1;  end ;
    if factor2 < 0 AND abs(factor2) >= &minloading then do; secfactor2 = 'f2'; secpolef2 = -1;  end ;
    if factor3 < 0 AND abs(factor3) >= &minloading then do; secfactor3 = 'f3'; secpolef3 = -1;  end ;
    if factor4 < 0 AND abs(factor4) >= &minloading then do; secfactor4 = 'f4'; secpolef4 = -1;  end ;
    if factor5 < 0 AND abs(factor5) >= &minloading then do; secfactor5 = 'f5'; secpolef5 = -1;  end ;
    if factor6 < 0 AND abs(factor6) >= &minloading then do; secfactor6 = 'f6'; secpolef6 = -1;  end ;
    if factor7 < 0 AND abs(factor7) >= &minloading then do; secfactor7 = 'f7'; secpolef7 = -1;  end ;
    if factor8 < 0 AND abs(factor8) >= &minloading then do; secfactor8 = 'f8'; secpolef8 = -1;  end ;
    if factor9 < 0 AND abs(factor9) >= &minloading then do; secfactor9 = 'f9'; secpolef9 = -1;  end ;

    if factor = secfactor1 then do; secfactor1 = ' ' ; end;
    if factor = secfactor2 then do; secfactor2 = ' ' ; end;
    if factor = secfactor3 then do; secfactor3 = ' ' ; end;
    if factor = secfactor4 then do; secfactor4 = ' ' ; end;
    if factor = secfactor5 then do; secfactor5 = ' ' ; end;
    if factor = secfactor6 then do; secfactor6 = ' ' ; end;
    if factor = secfactor7 then do; secfactor7 = ' ' ; end;
    if factor = secfactor8 then do; secfactor8 = ' ' ; end;
    if factor = secfactor9 then do; secfactor9 = ' ' ; end;
run;


/* Delete temporary TEMP_ tables only if any exist */
%let names=;

proc sql noprint;
    select memname into :names separated by ' '
    from dictionary.tables
    where libname = 'WORK'
      and substr(memname, 1, 5) = 'TEMP_';
quit;

%macro deltemp_rotint;
    %if %superq(names) ne %then %do;
        proc datasets library=work nolist;
            delete &names;
        quit;
    %end;
    %else %do;
        %put NOTE: No TEMP_ tables found for deletion after rotatedinterpr.;
    %end;
%mend deltemp_rotint;

%deltemp_rotint;


/* Create interpretation tables */
%macro create_interpretation_tables(howmany);
%do i=1 %to &howmany;

data temp_f&i._prim_pos
    (keep = Factor&i factor pole type table _NAME_
     rename = (Factor&i=loading));
    set rotated4 (where=(factor = "f&i" AND pole = 1));
    type = 'primary';
    table = "f&i.pos" ;
run;

proc sort data=temp_f&i._prim_pos;
    by descending loading;
run;

data temp_f&i._sec_pos
    (keep = Factor&i secfactor&i secpolef&i type table _NAME_
     rename = (Factor&i=loading secfactor&i=factor secpolef&i=pole));
    set rotatedinterpr (where=(secfactor&i = "f&i" AND secpolef&i = 1));
    type = 'secondary';
    table = "f&i.pos" ;
run;

proc sort data=temp_f&i._sec_pos;
    by descending loading;
run;

data temp_f&i._prim_neg
    (keep = Factor&i factor pole type table _NAME_
     rename = (Factor&i=loading));
    set rotated4 (where=(factor = "f&i" AND pole = -1));
    type = 'primary';
    table = "f&i.neg" ;
run;

proc sort data=temp_f&i._prim_neg;
    by loading;
run;

data temp_f&i._sec_neg
    (keep = Factor&i secfactor&i secpolef&i type table _NAME_
     rename = (Factor&i=loading secfactor&i=factor secpolef&i=pole));
    set rotatedinterpr (where=(secfactor&i = "f&i" AND secpolef&i = -1));
    type = 'secondary';
    table = "f&i.neg" ;
run;

proc sort data=temp_f&i._sec_neg;
    by loading;
run;

%end;
%mend create_interpretation_tables;

%create_interpretation_tables(&extractfactors)
quit;


/* Combine interpretation tables */
proc sql;
  create table mytables as
  select *
  from dictionary.tables
  where libname = "WORK"
    and substr(memname, 1, 6) = 'TEMP_F'
  order by memname ;
quit;

%let names=;

proc sql noprint;
    select memname into :names separated by ' '
    from mytables;
quit;

%macro create_loadtableinterpr;

    %if %superq(names) ne %then %do;

        data loadtableinterpr (drop = factor pole);
            length type $15;
            set &names ;
        run;

    %end;
    %else %do;

        data loadtableinterpr;
            length _NAME_ $32 type $15 table $15 loading 8;
            stop;
        run;

        %put NOTE: No TEMP_F interpretation tables found. Empty loadtableinterpr created.;

    %end;

%mend create_loadtableinterpr;

%create_loadtableinterpr;

ODS EXCLUDE NONE;
ods html file="&whereisit/&myfolder/loadtable_for_interpretation.html";
PROC PRINT data=loadtableinterpr ;
    FORMAT _NAME_ $featurelabels. loading 9.2 ;
run;
ods html close;

PROC EXPORT
  DATA= WORK.loadtableinterpr
  DBMS=CSV
  OUTFILE="&whereisit/&myfolder/loadtable_for_interpretation.csv"
  REPLACE;
RUN;


/* Delete temporary TEMP_ tables only if any exist */
%let names=;

proc sql noprint;
    select memname into :names separated by ' '
    from dictionary.tables
    where libname = 'WORK'
      and substr(memname, 1, 5) = 'TEMP_';
quit;

%macro deltemp_loadint;
    %if %superq(names) ne %then %do;
        proc datasets library=work nolist;
            delete &names;
        quit;
    %end;
    %else %do;
        %put NOTE: No TEMP_ tables found for deletion after loadtableinterpr export.;
    %end;
%mend deltemp_loadint;

%deltemp_loadint;


/* Adding metadata */
DATA &project._meta;
    SET &project ;
RUN;


/* ==========================================================================
   SECTION 7: SCORING
   ========================================================================== */

ODS EXCLUDE NONE;
ods html file="&whereisit/&myfolder/scoring.html";
proc print data=rotated3 ; run;
ods html close;
ODS EXCLUDE ALL;


/* Automatic scoring */

/* Standardize the same feature set used in the final factor model.

   The dataset &project._sum_check excludes:
   - wcount;
   - summary variables v900-v919;
   - zero-variance variables;
   - low-communality variables.

   Character metadata variables such as filename and subcorpus are retained
   automatically and are not standardized. */
PROC STDIZE DATA=&project._sum_check METHOD=STD OUT=mdz OUTSTAT=meta_stats;
    var _NUMERIC_ ;
RUN;


/* Factor scores */
data rotated4;
    set rotated3;
    if loaded = 1;
run;

proc sort data=rotated4;
    by factor ;
run;

proc transpose data=rotated4 out=score;
    by factor ;
    id _NAME_ ;
    var pole;
run;

data score;
    _type_='SCORE';
    set score;
    drop _name_;
    rename factor=_name_;
run;


/* Score the corpus */
proc score data=mdz score=score out=scores;
run;

proc sort data=scores;
    by filename;
run;


/* Keep only the columns needed for interpretation/statistical testing */
DATA scores_only
    (KEEP = filename subcorpus &factorvars);
    SET scores;
RUN;


/* Preserve downstream dataset names used by Section 8 */
DATA scores_combined;
    SET scores;
RUN;

DATA scores_only_combined;
    SET scores_only;
RUN;


/* Overview of corpus */
ODS EXCLUDE NONE;
ods html file="&whereisit/&myfolder/corpus_size.html";

proc freq data=&project;
    tables subcorpus / nocum;
run;

proc means data=&project sum mean min max stddev;
    class subcorpus;
    var wcount;
run;

ods html close;
ODS EXCLUDE ALL;


/* TMDA exports */
PROC EXPORT
    DATA=WORK.scores
    DBMS=CSV
    OUTFILE="&whereisit/&myfolder/&project._scores.csv"
    REPLACE;
RUN;

PROC EXPORT
    DATA=WORK.scores_only
    DBMS=CSV
    OUTFILE="&whereisit/&myfolder/&project._scores_only.csv"
    REPLACE;
RUN;


/* ==========================================================================
   SECTION 8: OUTLIER IDENTIFICATION FOR DIAGNOSTIC INSPECTION
   ========================================================================== */

/* --------------------------------------------------------------------------
   Outlier handling

   Outliers are identified separately for each factor score using the IQR rule.
   The outlier lists are exported for qualitative inspection.

   IMPORTANT:
   In this version of the script, the outlier-removal bypass is intentionally
   active. Therefore, outliers are NOT removed from the final statistical
   analyses or from the scores used for ranking compositions.

   The exported outlier files should be interpreted as diagnostic files.
   -------------------------------------------------------------------------- */

%let multipl=1;


/* Identify outlier texts for each factor */
%macro identify_outliers(howmany);

%do i=1 %to &howmany;

    %let VariableOfInterest=f&i;
    %let dsn=scores_combined;

    data temp;
        set &dsn;
    run;

    proc univariate data=temp noprint;
        var &VariableOfInterest;
        output out=IQRData
            Q1=Q1
            Q3=Q3
            QRANGE=IQR;
    run;

    proc sql noprint;
        select
            Q1 - &multipl * IQR,
            Q3 + &multipl * IQR
        into
            :lowerfence trimmed,
            :upperfence trimmed
        from IQRData;
    quit;

    %put NOTE: For &VariableOfInterest, outliers are observations below &lowerfence or above &upperfence.;

    data outliers_f&i;
        set temp;
        if &VariableOfInterest gt &upperfence
            or &VariableOfInterest lt &lowerfence;
    run;

%end;

%mend identify_outliers;

%identify_outliers(&extractfactors);
quit;


/* Isolate all outlier texts for possible removal */
data outliers_to_del
    (keep=filename subcorpus &factorvars);
    set outliers_f1 - outliers_f&extractfactors;
run;

proc sort data=outliers_to_del nodupkey;
    by filename subcorpus;
run;


/* Create outlier-trimmed dataset */
data &project._no_outliers;
    set scores_combined;
run;

proc sql;
    delete from &project._no_outliers as a
    where exists (
        select 1
        from outliers_to_del as b
        where a.filename = b.filename
          and a.subcorpus = b.subcorpus
    );
quit;


/* Save outlier lists by factor */
%macro export_outliers(howmany);

%do i=1 %to &howmany;

    data outliers_f&i
        (keep=filename subcorpus f&i);
        set outliers_f&i;
    run;

    proc sort data=outliers_f&i;
        by f&i;
    run;

    PROC EXPORT
        DATA=WORK.outliers_f&i
        DBMS=CSV
        OUTFILE="&whereisit/&myfolder/outliers_f&i..csv"
        REPLACE;
    RUN;

%end;

%mend export_outliers;

%export_outliers(&extractfactors);
quit;


/* Save combined outlier list */
PROC EXPORT
    DATA=WORK.outliers_to_del
    DBMS=CSV
    OUTFILE="&whereisit/&myfolder/outliers_all.csv"
    REPLACE;
RUN;


/* ========================================================================= */
/* ⚠️ OPTIONAL BYPASS: OUTLIER REMOVAL                                       */
/* ------------------------------------------------------------------------- */
/* The bypass is intentionally active in this analysis.                       */
/*                                                                           */
/* Therefore, &project._no_outliers is overwritten with the full scored       */
/* corpus, and outliers are retained in the final ANOVAs, boxplots, and      */
/* ranking workflow.                                                         */
/* ========================================================================= */

data &project._no_outliers;
    set scores_combined;
run;


/* ==========================================================================
   SECTION 9: STATISTICAL ANALYSIS (ANOVAs & BOXPLOTS)
   ========================================================================== */

/* Because the outlier bypass is active, &project._no_outliers currently
   contains the full scored corpus, including outliers. */

/* --------------------------------------------------------------------------
   Statistical analysis

   This section compares factor scores across subcorpora.

   Expected grouping variable:
   - subcorpus

   Expected dependent variables:
   - f1-f&extractfactors
   -------------------------------------------------------------------------- */


/* ANOVAs by subcorpus */

ODS EXCLUDE NONE;
ods html file="&whereisit/&myfolder/glm_meta.html";

%macro run_anovas(howmany);

%do i=1 %to &howmany;

    OPTIONS VALIDVARNAME=ANY;
    ods graphics off;

    title "GLM for dataset = &project._no_outliers: f&i by subcorpus";

    proc GLM data=&project._no_outliers;
        class subcorpus;
        model f&i = subcorpus;
        means subcorpus;
        ods output
            FitStatistics = r2_subcorpus_f&i
            OverallANOVA  = anova_subcorpus_f&i
            Means         = means_subcorpus_f&i;
    run;
    quit;

    title;

    ods graphics on;

%end;

%mend run_anovas;

%run_anovas(&extractfactors);

ods html close;
ODS EXCLUDE ALL;


/* Export ANOVA tables */

%macro export_anovas(howmany);

%do i=1 %to &howmany;

    PROC EXPORT
        DATA=WORK.r2_subcorpus_f&i
        DBMS=CSV
        OUTFILE="&whereisit/&myfolder/r2_subcorpus_f&i..csv"
        REPLACE;
    RUN;

    PROC EXPORT
        DATA=WORK.anova_subcorpus_f&i
        DBMS=CSV
        OUTFILE="&whereisit/&myfolder/anova_subcorpus_f&i..csv"
        REPLACE;
    RUN;

    PROC EXPORT
        DATA=WORK.means_subcorpus_f&i
        DBMS=CSV
        OUTFILE="&whereisit/&myfolder/means_subcorpus_f&i..csv"
        REPLACE;
    RUN;

%end;

%mend export_anovas;

%export_anovas(&extractfactors);


/* Boxplots by subcorpus */

ODS EXCLUDE NONE;

%macro create_boxplots(howmany);

%do i=1 %to &howmany;

    ods listing gpath="&whereisit/&myfolder/";
    ods graphics / imagename="boxplot_f&i" imagefmt=png reset=index;

    title "Boxplot of f&i by subcorpus";

    proc sgplot data=&project._no_outliers;
        vbox f&i / category=subcorpus;
        xaxis label="Subcorpus";
        yaxis label="Factor &i score";
    run;

    title;

%end;

%mend create_boxplots;

%create_boxplots(&extractfactors);

ODS EXCLUDE ALL;


/* ==========================================================================
   ZIP OUTPUT FILES
   ========================================================================== */

%let addcntzip = /home/u63529080/zip/output_&project..zip;

FILENAME temp "&addcntzip";

DATA _NULL_;
  rc=FDELETE('temp');
RUN;

data filelist;
run;

data filelist;
  length root dname $ 2048 filename $ 256 dir level 8;
  input root;
  retain filename dname ' ' level 0 dir 1;
cards4;
/home/u63529080/cl_st1_ph3_ednalvo
;;;;
run;

data filelist;
  modify filelist;
  rc1=filename('tmp',catx('/',root,dname,filename));
  rc2=dopen('tmp');
  dir = 1 & rc2;

  if dir then do;
      dname=catx('/',dname,filename);
      filename=' ';
  end;

  replace;

  if dir;

  level=level+1;

  do i=1 to dnum(rc2);
    filename=dread(rc2,i);
    output;
  end;

  rc3=dclose(rc2);
run;

proc sort data=filelist;
  by root dname filename;
run;

proc print data=filelist;
run;

data _null_;

  set filelist;

  if dir=0;

  rc1=filename("in" , catx('/',root,dname,filename), "disk", "lrecl=1 recfm=n");
  rc1txt=sysmsg();

  rc2=filename(
      "out",
      "&addcntzip.",
      "ZIP",
      "lrecl=1 recfm=n member='" !! catx('/',dname,filename) !! "'"
  );
  rc2txt=sysmsg();

  do _N_ = 1 to 6;
    rc3=fcopy("in","out");
    rc3txt=sysmsg();

    if fexist("out") then leave;
    else sleeprc=sleep(0.5,1);
  end;

  rc4=fexist("out");
  rc4txt=sysmsg();

  put _N_ @12 (rc:) (=);

run;


/* Delete top-level png, html, tsv, and csv files after zipping.

   Note:
   This cleanup scans only &whereisit/&myfolder, not subdirectories.
   Input files stored in subdirectories are not deleted by this step. */

%let path=&whereisit/&myfolder;

FILENAME _folder_ "%bquote(&path.)";

data filenames(keep=memname);
  handle=dopen( '_folder_' );

  if handle > 0 then do;
    count=dnum(handle);

    do i=1 to count;
      memname=dread(handle,i);

      if scan(memname, 2, '.')='png'
      OR scan(memname, 2, '.')='html'
      OR scan(memname, 2, '.')='tsv'
      OR scan(memname, 2, '.')='csv'
      then output filenames;
    end;
  end;

  rc=dclose(handle);
run;

filename _folder_ clear;

data _null_;
set filenames;
fname = 'todelete';
rc = filename(fname, quote(cats("&path",'/',memname)));
rc = fdelete(fname);
rc = filename(fname);
run;


/* END OF PROGRAM */