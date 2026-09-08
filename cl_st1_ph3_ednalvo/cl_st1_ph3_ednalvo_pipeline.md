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
  --prompt prompts_de_geracao_de_composicoes/geracao_de_composicao_v1.md
```

### Full run mode

```shell script
python gere_llm_resumo_ou_composicao.py componha \
  --input-dir corpus/02_resumos \
  --output-dir corpus/01_composicoes/menores_notas_gpt \
  --model gpt-5.6-sol \
  --prompt prompts_de_geracao_de_composicoes/geracao_de_composicao_v1.md
```

## 3. Generate compositions Gemini

```shell script
python gere_llm_resumo_ou_composicao.py componha \
  --input-dir corpus/02_resumos \
  --output-dir corpus/01_composicoes/menores_notas_gemini \
  --model gemini-3.6-flash \
  --prompt prompts_de_geracao_de_composicoes/geracao_de_composicao_v1.md
```
