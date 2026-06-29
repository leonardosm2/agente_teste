# Agente ABC — Antecipação Avulsa

Agente conversacional CLI para análise do teste ABC de precificação, construído com LangChain + OpenAI (GPT-4o).

## Setup

```bash
pip install langchain langchain-openai langchain-core pandas numpy
export OPENAI_API_KEY="sk-..."
python agent.py
```

## Arquivos

| Arquivo | Descrição |
|---|---|
| `agent.py` | Agente principal — loop CLI, tools, system prompt |
| `abc_functions.py` | Mock das funções de negócio — **substituir pelo real** |

## Substituindo o mock

Em `agent.py`, linha de import:
```python
from abc_functions import get_data, fill_data, get_policy, to_json
```
Troque `abc_functions` pelo seu módulo real. As assinaturas esperadas são:

```python
get_data() -> pd.DataFrame
fill_data(update: int, rating_na: bool, rating_not_na: bool, df: pd.DataFrame) -> pd.DataFrame
get_policy() -> pd.DataFrame
to_json(df_policy: pd.DataFrame) -> str
```

## Fluxo típico de uso

```
1. Agente carrega dados e política automaticamente
2. Usuário pede análise por segmento/ajuste
3. Agente filtra dados, analisa perf_a/b/c e sugere ajustes de spread
4. Usuário aprova ou nega cada sugestão
5. Agente edita df_policy apenas após confirmação explícita
6. Usuário pede "mostra como ficou a política"
7. Usuário pede o JSON → agente gera e exibe
```

## Exemplos de comandos

- "Analisa os dados após o segundo ajuste, só para clientes com rating"
- "Onde você vê oportunidade de subir o spread no segmento de porte?"
- "Aprovado, aplica o ajuste para micro"
- "Não, para pequeno mantém como está"
- "Como ficou a política com os ajustes aprovados?"
- "Gera o JSON"

## Trocar o modelo

Em `agent.py`, na função `run_agent()`:
```python
llm = ChatOpenAI(model="gpt-4o", ...)  # troque por gpt-4o-mini, gpt-4-turbo etc.
```
