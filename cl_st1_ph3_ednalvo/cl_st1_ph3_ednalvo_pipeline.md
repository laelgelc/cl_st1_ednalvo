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
  --tagset gelc_llm_taggers/tagset_ptbr.md
```
