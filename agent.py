"""
Agente conversacional para análise do teste ABC em antecipação avulsa.
Uso: python agent.py
Requer: OPENAI_API_KEY no ambiente
"""

import os
import json
import re
import textwrap
from typing import Optional
import pandas as pd

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool

# ── Importa as funções de negócio (troque pelo import real em produção) ──────
from abc_functions import get_data, fill_data, get_policy, to_json

from rich.console import Console
from rich.markdown import Markdown

console = Console()

# ── Estado global da sessão ──────────────────────────────────────────────────
class SessionState:
    df_raw: Optional[pd.DataFrame] = None          # dados brutos
    df_filtered: Optional[pd.DataFrame] = None     # dados filtrados
    df_policy: Optional[pd.DataFrame] = None       # política (mutável pelo agente)
    pending_changes: list[dict] = []               # sugestões pendentes de aprovação


state = SessionState()


# ── Ferramentas (Tools) ──────────────────────────────────────────────────────

@tool
def tool_get_data() -> str:
    """
    Carrega (ou recarrega) os dados brutos do teste ABC.
    Deve ser chamada no início da sessão ou quando o usuário solicitar atualização dos dados.
    Retorna um resumo do volume de dados carregados.
    """
    state.df_raw = get_data()
    shape = state.df_raw.shape
    clusters = state.df_raw[["tipo_cluster", "cluster"]].drop_duplicates().shape[0]
    ajustes = 4
    return (
        f"Dados carregados com sucesso. "
        f"{shape[0]} registros × {shape[1]} colunas. "
        f"{clusters} combinações tipo_cluster/cluster. "
        f"Ajustes disponíveis: {ajustes}."
    )


@tool
def tool_fill_data(update: int = 0, rating_na: bool = True, rating_not_na: bool = True) -> str:
    """
    Filtra os dados do teste ABC e armazena o resultado na sessão.

    Args:
        update: após qual ajuste de preço filtrar (0 = sem filtro de ajuste, 1 = após 1º ajuste, etc.)
        rating_na: incluir segmentos sem rating (padrão True)
        rating_not_na: incluir segmentos com rating (padrão True)

    Returns:
        Tabela formatada com os dados filtrados.
    """
    if state.df_raw is None:
        return "ERRO: dados brutos não carregados. Chame tool_get_data primeiro."

    if not rating_na and not rating_not_na:
        return "ERRO: pelo menos um dos flags rating_na ou rating_not_na deve ser True."

    state.df_filtered = fill_data(update, rating_na, rating_not_na, state.df_raw)

    if state.df_filtered.empty:
        return "Nenhum dado encontrado para os filtros aplicados."

    summary = state.df_filtered.to_string(index=False)
    n = len(state.df_filtered)
    return (
        f"Filtro aplicado: ajuste>={update}, rating_na={rating_na}, rating_not_na={rating_not_na}.\n"
        f"{n} segmentos retornados:\n\n{summary}"
    )


@tool
def tool_get_policy() -> str:
    """
    Carrega a política de preços original (inc_absoluto, inc_percentual) e o
    incremento do teste (inc_teste). Armazena na sessão para edições posteriores.
    Retorna a tabela completa da política.
    """
    state.df_policy = get_policy()
    return (
        f"Política carregada. {len(state.df_policy)} segmentos.\n\n"
        + state.df_policy.to_string(index=False)
    )


@tool
def tool_update_policy(tipo_cluster: str, cluster: str, novo_inc_teste: float) -> str:
    """
    Aplica um ajuste aprovado ao inc_teste de um segmento específico na política.
    Use apenas após o usuário confirmar explicitamente a sugestão.

    Args:
        tipo_cluster: tipo do cluster (ex: "volume", "rating", "segmento")
        cluster: nome do cluster (ex: "micro", "alimentacao")
        novo_inc_teste: novo valor de inc_teste a aplicar (formato numérico, ex.: 5% = 0.05)

    Returns:
        Confirmação da atualização e linha modificada.
    """
    if state.df_policy is None:
        return "ERRO: política não carregada. Chame tool_get_policy primeiro."

    mask = (
        (state.df_policy["tipo_cluster"] == tipo_cluster) &
        (state.df_policy["cluster"] == cluster)
    )

    if not mask.any():
        return f"ERRO: segmento '{tipo_cluster}/{cluster}' não encontrado na política."

    old_val = state.df_policy.loc[mask, "inc_teste"].values[0]
    state.df_policy.loc[mask, "inc_teste"] = round(novo_inc_teste, 4)

    row = state.df_policy[mask].to_string(index=False)
    return (
        f"Política atualizada: {tipo_cluster}/{cluster} | "
        f"inc_teste: {old_val} → {novo_inc_teste}\n\n{row}"
    )


@tool
def tool_show_updated_policy() -> str:
    """
    Exibe a política atual com todos os ajustes já aprovados pelo usuário.
    """
    if state.df_policy is None:
        return "ERRO: política não carregada. Chame tool_get_policy primeiro."
    return "Política com ajustes aplicados:\n\n" + state.df_policy.to_string(index=False)


@tool
def tool_to_json() -> str:
    """
    Serializa a política com o inc_teste atualizado para JSON.
    Deve ser chamada apenas após o usuário confirmar que finalizou os ajustes.
    Returns:
        JSON string com a política atualizada.
    """
    if state.df_policy is None:
        return "ERRO: política não carregada. Chame tool_get_policy primeiro."
    result = to_json(state.df_policy)
    return f"JSON da política atualizada:\n\n{result}"


# ── System Prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Você é um analista quantitativo especialista em testes de precificação (Teste ABC) \
para antecipação avulsa em meios de pagamento. Você é direto, técnico e preciso.

## Seu contexto
Você analisa um experimento onde lojistas foram divididos em 3 grupos:
- **Grupo A**: opera com spread **-15%** em relação ao spread base (controle mais barato)
- **Grupo B**: opera com spread **base** (grupo de controle central)
- **Grupo C**: opera com spread **+15%** em relação ao spread base (controle mais caro)

O indicador de performance (**perf**) = receita líquida do grupo / número de lojistas.
Quanto maior o perf, melhor a rentabilidade por lojista naquele segmento.

## Ferramentas disponíveis
- `tool_get_data`: carrega/recarrega dados brutos
- `tool_fill_data(update, rating_na, rating_not_na)`: filtra e exibe dados
- `tool_get_policy`: carrega política de preços
- `tool_update_policy(tipo_cluster, cluster, novo_inc_teste)`: edita inc_teste de um segmento
- `tool_show_updated_policy`: mostra política com ajustes aplicados
- `tool_to_json`: gera JSON final da política atualizada

## Regras de comportamento
1. **Seja técnico e preciso.** Se não tiver certeza sobre a intenção do usuário (ex: qual ajuste, qual segmento), pergunte antes de agir.
2. **Análise de oportunidade**: compare perf_a, perf_b e perf_c para inferir elasticidade de preço:
   - perf_c >> perf_b: lojistas do segmento toleram spread mais alto → oportunidade de **subir** spread
   - perf_a >> perf_b e perf_c < perf_b: demanda sensível a preço → considere **manter ou reduzir** spread
   - perf_b dominante: equilíbrio, avaliar com cautela
3. **Sugestões**: sempre fundamente com os dados (perf_a, perf_b, perf_c, qtd_pvs). Nunca sugira ajuste sem evidência nos dados filtrados.
4. **Aprovação obrigatória**: só chame `tool_update_policy` quando o usuário **confirmar explicitamente** (ex: "pode aplicar", "aprovado", "sim, aplica"). Em caso de dúvida, pergunte.
5. **Negação**: se o usuário negar uma sugestão, registre mentalmente e não aplique.
6. **JSON**: só gere o JSON quando o usuário solicitar explicitamente.
7. Se os dados não estiverem carregados e o usuário fizer uma análise, carregue-os automaticamente antes de responder.

## Início de sessão
Ao iniciar, apresente-se brevemente, carregue os dados e a política automaticamente, e pergunte por qual corte de dados o usuário quer começar.
"""

# ── Loop do agente ────────────────────────────────────────────────────────────

TOOLS = [
    tool_get_data,
    tool_fill_data,
    tool_get_policy,
    tool_update_policy,
    tool_show_updated_policy,
    tool_to_json,
]

TOOL_MAP = {t.name: t for t in TOOLS}


def run_agent():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERRO: variável de ambiente OPENAI_API_KEY não definida.")
        return

    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        api_key=api_key,
    ).bind_tools(TOOLS)

    messages: list = [SystemMessage(content=SYSTEM_PROMPT)]

    print("\n" + "═" * 60)
    print("  Agente ABC — Antecipação Avulsa  |  Teste de Precificação")
    print("═" * 60)
    print("  Digite 'sair' para encerrar.\n")

    # Kick-off: apresentação + carga de dados (com ciclo completo de tool-calls)
    messages.append(HumanMessage(content="[SISTEMA] Iniciar sessão."))
    _run_turn(llm, messages)

    # Loop principal
    while True:
        try:
            user_input = input("\n👤 Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nEncerrando sessão.")
            break

        if user_input.lower() in ("sair", "exit", "quit"):
            print("Sessão encerrada.")
            break

        if not user_input:
            continue

        messages.append(HumanMessage(content=user_input))
        _run_turn(llm, messages)


def _run_turn(llm, messages):
    """
    Executa um turno completo: invoca o LLM e processa todos os tool-calls
    em loop até o modelo retornar uma resposta só de texto.
    Garante que cada tool_call_id tenha seu ToolMessage correspondente.
    """
    while True:
        response = llm.invoke(messages)
        messages.append(response)

        tool_calls = getattr(response, "tool_calls", None)
        if not tool_calls:
            _print_ai(response.content)
            return

        # Executa TODAS as tool calls antes de invocar o LLM novamente
        for tc in tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            tool_id = tc["id"]

            print(f"\n  ⚙️  [{tool_name}] args={tool_args}")

            if tool_name in TOOL_MAP:
                try:
                    result = TOOL_MAP[tool_name].invoke(tool_args)
                except Exception as e:
                    result = f"ERRO ao executar {tool_name}: {e}"
            else:
                result = f"ERRO: ferramenta '{tool_name}' não encontrada."

            messages.append(
                ToolMessage(content=str(result), tool_call_id=tool_id)
            )


def _print_ai(content: str):
    if not content:
        return

    console.print()
    console.print("[bold cyan]🤖 Agente[/bold cyan]")
    console.print()

    console.print(Markdown(content))


if __name__ == "__main__":
    run_agent()