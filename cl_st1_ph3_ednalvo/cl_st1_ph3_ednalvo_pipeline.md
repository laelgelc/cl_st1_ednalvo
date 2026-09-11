# Corpus Linguistics - Study 1 - Phase 3 - Ednalvo

Run the commands from the project phase directory, e.g.:

```text
cl_st1_ph3_ednalvo/
```

## 1. Summarise compositions

```shell script
python gere_llm_resumo_ou_composicao.py resuma \
  --input-dir corpus/01_composicoes/menores_notas \
  --output-dir corpus/02_resumos \
  --model gpt-5.6-sol \
  --prompt prompts_de_geracao_de_composicoes/resumo_de_composicao_v1.md
```

## 2. Generate compositions GPT

### Test mode

```shell script
python gere_llm_resumo_ou_composicao.py componha \
  --input-dir corpus/02_resumos \
  --output-dir corpus/01_composicoes/menores_notas_gpt \
  --model gpt-5.6-sol \
  --prompt prompts_de_geracao_de_composicoes/geracao_de_composicao_v1.md \
  --test-mode
```

### Full run

```shell script
python gere_llm_resumo_ou_composicao.py componha \
  --input-dir corpus/02_resumos \
  --output-dir corpus/01_composicoes/menores_notas_gpt \
  --model gpt-5.6-sol \
  --prompt prompts_de_geracao_de_composicoes/geracao_de_composicao_v1.md
```

### Production mode on an EC2 instance

```shell script
bash run_python_ec2.sh \
    gere_llm_resumo_ou_composicao.py componha \
  --input-dir corpus/02_resumos \
  --output-dir corpus/01_composicoes/menores_notas_gpt \
  --model gpt-5.6-sol \
  --prompt prompts_de_geracao_de_composicoes/geracao_de_composicao_v1.md
```

## 3. Generate compositions Gemini

### Test mode

```shell script
python gere_llm_resumo_ou_composicao.py componha \
  --input-dir corpus/02_resumos \
  --output-dir corpus/01_composicoes/menores_notas_gemini \
  --model gemini-3.6-flash \
  --prompt prompts_de_geracao_de_composicoes/geracao_de_composicao_v1.md \
  --test-mode
```

## Full run

```shell script
python gere_llm_resumo_ou_composicao.py componha \
  --input-dir corpus/02_resumos \
  --output-dir corpus/01_composicoes/menores_notas_gemini \
  --model gemini-3.6-flash \
  --prompt prompts_de_geracao_de_composicoes/geracao_de_composicao_v1.md
```

### Production mode on an EC2 instance

```shell script
bash run_python_ec2.sh \
    gere_llm_resumo_ou_composicao.py componha \
  --input-dir corpus/02_resumos \
  --output-dir corpus/01_composicoes/menores_notas_gemini \
  --model gemini-3.6-flash \
  --prompt prompts_de_geracao_de_composicoes/geracao_de_composicao_v1.md
```

## 4. Tag compositions with the GELC LLM Tagger

### Test run

```shell script
python anote_composicoes.py \
  --input-dir corpus/01_composicoes \
  --output-dir corpus/03_composicoes_anotadas \
  --model gpt-5.6-sol \
  --prompt gelc_llm_taggers/llm_tagging_prompt.md \
  --tagset gelc_llm_taggers/tagset_ptbr.md \
  --test-mode
```

```shell script
python anote_composicoes.py \
  --input-dir corpus/01_composicoes \
  --output-dir corpus/03_composicoes_anotadas \
  --model gemini-3.6-flash \
  --prompt gelc_llm_taggers/llm_tagging_prompt.md \
  --tagset gelc_llm_taggers/tagset_ptbr.md \
  --test-mode \
  --test-limit 10
```

### Full run

```shell script
python anote_composicoes.py \
  --input-dir corpus/01_composicoes \
  --output-dir corpus/03_composicoes_anotadas \
  --model gpt-5.6-sol \
  --prompt gelc_llm_taggers/llm_tagging_prompt.md \
  --tagset gelc_llm_taggers/tagset_ptbr.md
```

### Production mode on an EC2 instance

```shell script
bash run_python_ec2.sh \
    anote_composicoes.py \
  --input-dir corpus/01_composicoes \
  --output-dir corpus/03_composicoes_anotadas \
  --model gpt-5.6-sol \
  --prompt gelc_llm_taggers/llm_tagging_prompt.md \
  --tagset gelc_llm_taggers/tagset_ptbr.md \
  --workers 10
```

## 5. Compute the Normed Document Feature Matrix

```shell script
python compute_dfm_normalizado.py \
  --input-dir corpus/03_composicoes_anotadas/maiores_notas \
  --output-dir sas/maiores_notas_counts.tsv \
  --tagset gelc_llm_taggers/tagset_ptbr.md
```

```shell script
python compute_dfm_normalizado.py \
  --input-dir corpus/03_composicoes_anotadas/menores_notas \
  --output-dir sas/menores_notas_counts.tsv \
  --tagset gelc_llm_taggers/tagset_ptbr.md
```

```shell script
python compute_dfm_normalizado.py \
  --input-dir corpus/03_composicoes_anotadas/menores_notas_gemini \
  --output-dir sas/menores_notas_gemini_counts.tsv \
  --tagset gelc_llm_taggers/tagset_ptbr.md
```

```shell script
python compute_dfm_normalizado.py \
  --input-dir corpus/03_composicoes_anotadas/menores_notas_gpt \
  --output-dir sas/menores_notas_gpt_counts.tsv \
  --tagset gelc_llm_taggers/tagset_ptbr.md
```
## 6. Run SAS

## 7. Generate Markdown example extracts

```shell script
python examples_md.py
```

Output: `examples_md/`

```shell script
(my_env) eyamrog@eyamrog-Vivobook-16:~/PycharmProjects/cl_st1_ednalvo/cl_st1_ph3_ednalvo$ python examples_md.py
Project: cl_st1_ph3_ednalvo
Scores file: sas/output_cl_st1_ph3_ednalvo/cl_st1_ph3_ednalvo_scores_only.csv
Corpus dir: corpus/01_composicoes
Loadtable: sas/output_cl_st1_ph3_ednalvo/loadtable_for_interpretation.csv
Detected 4 factors: f1, f2, f3, f4.

→ f1_pos: selecting by subcorpus means (ranked: menores_notas, maiores_notas, menores_notas_gpt, menores_notas_gemini)
  ✓ Wrote 50 examples for f1_pos

→ f1_neg: selecting by subcorpus means (ranked: menores_notas_gemini, menores_notas_gpt, maiores_notas, menores_notas)
  ✓ Wrote 50 examples for f1_neg

→ f2_pos: selecting by subcorpus means (ranked: menores_notas, maiores_notas, menores_notas_gemini, menores_notas_gpt)
  ✓ Wrote 50 examples for f2_pos

→ f2_neg: selecting by subcorpus means (ranked: menores_notas_gpt, menores_notas_gemini, maiores_notas, menores_notas)
  ✓ Wrote 50 examples for f2_neg

→ f3_pos: selecting by subcorpus means (ranked: menores_notas_gpt, menores_notas, maiores_notas, menores_notas_gemini)
  ✓ Wrote 50 examples for f3_pos

→ f3_neg: selecting by subcorpus means (ranked: menores_notas_gemini, maiores_notas, menores_notas, menores_notas_gpt)
  ✓ Wrote 50 examples for f3_neg

→ f4_pos: selecting by subcorpus means (ranked: maiores_notas, menores_notas, menores_notas_gpt, menores_notas_gemini)
  ✓ Wrote 50 examples for f4_pos

→ f4_neg: selecting by subcorpus means (ranked: menores_notas_gemini, menores_notas_gpt, menores_notas, maiores_notas)
  ✓ Wrote 50 examples for f4_neg

(my_env) eyamrog@eyamrog-Vivobook-16:~/PycharmProjects/cl_st1_ednalvo/cl_st1_ph3_ednalvo$ 
```

## 8. Generate Markdown ANOVA table

```shell script
python anova_table_md.py
```

Output: `anova_table_md/`

## 9. Generate assessments GPT

### Test mode

```shell script
python gere_llm_avaliacao.py avalie \
  --input-dir corpus/01_composicoes \
  --output-dir corpus/04_composicoes_avaliadas \
  --model gpt-5.6-sol \
  --prompt prompts_de_avaliacao_de_composicoes/avaliacao_de_composicao_v1.md \
  --test-mode
```

### Full run

```shell script
python gere_llm_avaliacao.py avalie \
  --input-dir corpus/01_composicoes \
  --output-dir corpus/04_composicoes_avaliadas \
  --model gpt-5.6-sol \
  --prompt prompts_de_avaliacao_de_composicoes/avaliacao_de_composicao_v1.md
```

### Production mode on an EC2 instance

```shell script
bash run_python_ec2.sh \
    gere_llm_avaliacao.py avalie \
  --input-dir corpus/01_composicoes \
  --output-dir corpus/04_composicoes_avaliadas \
  --model gpt-5.6-sol \
  --prompt prompts_de_avaliacao_de_composicoes/avaliacao_de_composicao_v1.md \
  --workers 10
```