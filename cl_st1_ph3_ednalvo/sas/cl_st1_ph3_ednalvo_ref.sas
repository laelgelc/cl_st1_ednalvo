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

/* Files will NOT be saved to the folder above unless you put in 'gelc.'
   before every destination. Otherwise files are created in WORK. */

options fmtsearch=(work library);
options validvarname=any;

/* Extraction & cutoff parameters */
%let extractfactors = 5 ;
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
   filename    subcorpus    v001 ... v006    v007_1-v007_4    v008-v230    v900-v919

   Notes:
   - filename and subcorpus are character variables.
   - all v* variables are numeric.
   - DLM='09'x specifies tab-delimited input.
   - FIRSTOBS=2 skips the header row.
   -------------------------------------------------------------------------- */

%macro import_dfm(dataset=, infile=);

DATA &dataset ;
    LENGTH filename $150 subcorpus $50;

    INFILE "&whereisit/&myfolder/sas/&infile"
        DLM='09'x
        DSD
        FIRSTOBS=2
        TRUNCOVER;

    INPUT
        filename :$150.
        subcorpus :$50.
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
   Summary-variable handling

   The 9xx variables are aggregate/summary variables derived from specific
   variables in the tagset. In traditional MDA/factor analysis, allowing a
   summary variable to coexist with the specific variables from which it is
   computed can introduce artificial covariance, overweight a linguistic domain,
   and complicate interpretation.

   In the present Portuguese tagset, some summary variables also overlap with
   one another, because the linguistic taxonomy is cross-classified. For example,
   a specific feature may belong both to a part-of-speech summary and to a
   stance, modality, clause-type, or PB-variation summary.

   Therefore, for the primary TMDA model, all summary variables v900-v919 are
   excluded from factor extraction. They may later be used descriptively or in a
   separate sensitivity analysis, but not in the main factor model.
   -------------------------------------------------------------------------- */

DATA &project._no_sum_v (
    DROP = v900-v919
);
    SET &project;
RUN;


/* ==========================================================================
   SECTION 4: UNROTATED FACTOR ANALYSIS & COMMUNALITY CUTOFF
   ========================================================================== */

/* --------------------------------------------------------------------------
   Unrotated factor analysis before dropping low-communality variables.

   This model uses only specific variables, because v900-v919 were removed in
   &project._no_sum_v.
   -------------------------------------------------------------------------- */

ODS EXCLUDE NONE;
ODS HTML FILE="&whereisit/&myfolder/unrotated.html";
ODS TRACE ON;

PROC FACTOR
    OUTSTAT=fout
    DATA=&project._no_sum_v
    METHOD=principal
    SCREE
    MINEIGEN=0
    NFACTORS=100
    PRIORS=smc
    HEYWOOD;
    VAR _NUMERIC_;
RUN;
QUIT;

ODS TRACE OFF;
ODS HTML CLOSE;
ODS EXCLUDE ALL;


/* Isolate communalities */
DATA fout2;
    SET fout (WHERE=(_TYPE_="COMMUNAL"));
RUN;


/* Transpose communalities so each linguistic variable has one row */
PROC TRANSPOSE DATA=fout2 OUT=communal;
    ID _TYPE_;
RUN;


/* Identify variables below the communality cutoff */
PROC SQL;
    SELECT _name_
        INTO :names SEPARATED BY ' '
    FROM communal
    WHERE communal < &communalcutoff ;
QUIT;


/* Drop low-communality variables */
DATA &project._no_low_c ;
    SET &project._no_sum_v ;
    DROP &names;
RUN;


/* Save dropped variables */
PROC SORT DATA=communal;
    BY _NAME_;
RUN;

DATA communal_dropped ;
    SET communal ;
    IF COMMUNAL < &communalcutoff ;
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
DATA fout2;
    SET fout (WHERE=(_TYPE_="EIGENVAL"));
RUN;

PROC TRANSPOSE DATA=fout2 OUT=fout3 (DROP=_NAME_);
    ID _TYPE_;
RUN;

DATA fout4 ;
    SET fout3 ;
    factor = _n_;
    IF factor <= 20 ;
RUN;

ODS EXCLUDE NONE;
ODS LISTING GPATH="&whereisit/&myfolder/";
ODS GRAPHICS / IMAGENAME="scree" IMAGEFMT=png;

TITLE "Scree plot";
PROC SGPLOT DATA=fout4 ;
    SERIES X=factor Y=EIGENVAL / DATALABEL=factor;
RUN;
TITLE;

ODS EXCLUDE ALL;


/* ==========================================================================
   SECTION 5: FINAL ROTATED FACTOR ANALYSIS
   ========================================================================== */

/* --------------------------------------------------------------------------
   The earlier additive-MDA script contained an intermediate Biber-style
   summary-variable check. That block is intentionally removed here.

   The final rotated factor analysis uses:
   - specific variables only;
   - summary variables v900-v919 excluded;
   - low-communality variables removed.
   -------------------------------------------------------------------------- */

DATA &project._sum_check ;
    SET &project._no_low_c ;
RUN;


ODS EXCLUDE NONE;
ODS HTML FILE="&whereisit/&myfolder/rotated.html";
ODS TRACE ON;

PROC FACTOR
    OUTSTAT=rotatedfinal
    DATA=&project._sum_check
    METHOD=principal
    SCREE
    MSA
    MINEIGEN=0
    PRIORS=smc
    NFACTORS=&extractfactors
    ROTATE=promax
    HEYWOOD;
    VAR _NUMERIC_;
RUN;
QUIT;

ODS TRACE OFF;
ODS HTML CLOSE;
ODS EXCLUDE ALL;


/* ==========================================================================
   SECTION 6: LOADINGS TABLE PREPARATION
   ========================================================================== */

/* Reformat OUTSTAT to obtain the rotated factor pattern */
DATA rotated_pattern;
    SET rotatedfinal (WHERE=(_TYPE_="PREROTAT"));
RUN;

PROC TRANSPOSE DATA=rotated_pattern OUT=rotated2;
    ID _NAME_;
RUN;


/* --------------------------------------------------------------------------
   Identify primary factor assignment for each variable.

   A variable is assigned to the factor on which it has the largest absolute
   loading, provided that loading is at least &minloading.

   pole =  1 means positive loading
   pole = -1 means negative loading
   loaded = 1 means the variable reached the loading threshold
   -------------------------------------------------------------------------- */

DATA rotated3;
    SET rotated2;

    ARRAY facs factor1-factor&extractfactors;

    loaded = 0;
    max_abs_loading = 0;
    factor_num = .;

    DO i = 1 TO DIM(facs);
        IF ABS(facs[i]) > max_abs_loading THEN DO;
            max_abs_loading = ABS(facs[i]);
            factor_num = i;
        END;
    END;

    IF max_abs_loading >= &minloading THEN DO;
        loaded = 1;
        factor = CATS('f', factor_num);

        IF facs[factor_num] > 0 THEN pole = 1;
        ELSE IF facs[factor_num] < 0 THEN pole = -1;
    END;

    DROP i factor_num max_abs_loading;
RUN;


/* Keep only variables that loaded for interpretation */
DATA rotated4;
    SET rotated3;
    IF loaded = 1;
RUN;


/* Export full rotated pattern with loading assignment information */
ODS EXCLUDE NONE;
PROC EXPORT
    DATA=WORK.rotated3
    DBMS=CSV
    OUTFILE="&whereisit/&myfolder/rotated.csv"
    REPLACE;
RUN;
ODS EXCLUDE ALL;


/* ==========================================================================
   SECTION 7: FACTOR LOADINGS TABLES
   ========================================================================== */

/* --------------------------------------------------------------------------
   Create primary loading tables by factor and pole.

   At this stage, variable names are v001, v002, v007_1, etc.
   Human-readable feature labels can be added later through PROC FORMAT after
   the final variable list is stable.
   -------------------------------------------------------------------------- */

ODS EXCLUDE NONE;
ODS HTML FILE="&whereisit/&myfolder/loadtable.html";

%macro print_loadings(howmany);

    %do i=1 %to &howmany;

        TITLE "LOADINGS TABLE";
        TITLE2 "Factor &i positive pole";

        DATA temp;
            SET rotated4;
            WHERE factor = "f&i" AND pole = 1;
        RUN;

        PROC SORT DATA=temp;
            BY DESCENDING Factor&i;
        RUN;

        PROC PRINT DATA=temp;
            VAR _NAME_ Factor&i;
        RUN;


        TITLE "LOADINGS TABLE";
        TITLE2 "Factor &i negative pole";

        DATA temp;
            SET rotated4;
            WHERE factor = "f&i" AND pole = -1;
        RUN;

        PROC SORT DATA=temp;
            BY Factor&i;
        RUN;

        PROC PRINT DATA=temp;
            VAR _NAME_ Factor&i;
        RUN;

    %end;

%mend print_loadings;

%print_loadings(&extractfactors)

ODS HTML CLOSE;
TITLE;


/* ==========================================================================
   SECTION 8: LOADINGS TABLE FOR INTERPRETATION EXPORT
   ========================================================================== */

/* --------------------------------------------------------------------------
   Create a compact CSV table of variables that loaded primarily on each factor.

   Columns:
   - _NAME_  = linguistic variable name
   - factor  = assigned factor
   - pole    = positive or negative pole
   - loading = loading on the assigned factor
   - table   = factor/pole label, e.g. f1.pos or f1.neg
   -------------------------------------------------------------------------- */

%macro create_loading_tables(howmany);

    %do i=1 %to &howmany;

        DATA temp_f&i._prim_pos (
            KEEP = _NAME_ factor pole loading table
        );
            SET rotated4 (WHERE=(factor = "f&i" AND pole = 1));
            loading = Factor&i;
            table = "f&i..pos";
        RUN;

        PROC SORT DATA=temp_f&i._prim_pos;
            BY DESCENDING loading;
        RUN;


        DATA temp_f&i._prim_neg (
            KEEP = _NAME_ factor pole loading table
        );
            SET rotated4 (WHERE=(factor = "f&i" AND pole = -1));
            loading = Factor&i;
            table = "f&i..neg";
        RUN;

        PROC SORT DATA=temp_f&i._prim_neg;
            BY loading;
        RUN;

    %end;

%mend create_loading_tables;

%create_loading_tables(&extractfactors)


PROC SQL;
    CREATE TABLE mytables AS
    SELECT *
    FROM dictionary.tables
    WHERE libname = "WORK"
      AND SUBSTR(memname, 1, 6) = "TEMP_F"
    ORDER BY memname;
QUIT;

PROC SQL;
    SELECT memname
        INTO :names SEPARATED BY ' '
    FROM mytables;
QUIT;


DATA loadtableinterpr;
    LENGTH table $15 factor $10;
    SET &names;
RUN;


ODS EXCLUDE NONE;
ODS HTML FILE="&whereisit/&myfolder/loadtable_for_interpretation.html";

PROC PRINT DATA=loadtableinterpr;
    FORMAT loading 9.2;
RUN;

ODS HTML CLOSE;


PROC EXPORT
    DATA=WORK.loadtableinterpr
    DBMS=CSV
    OUTFILE="&whereisit/&myfolder/loadtable_for_interpretation.csv"
    REPLACE;
RUN;


/* Clean temporary loading-table datasets */
PROC SQL;
    SELECT memname
        INTO :names SEPARATED BY ' '
    FROM dictionary.tables
    WHERE libname = "WORK"
      AND SUBSTR(memname, 1, 5) = "TEMP_";
QUIT;

PROC DATASETS LIBRARY=work NOLIST;
    DELETE &names;
RUN;
QUIT;


/* ==========================================================================
   END OF CURRENT TMDA REVISION
   ========================================================================== */