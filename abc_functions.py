"""
Funções de negócio do teste ABC em antecipação avulsa.
"""

import pandas as pd


def get_data() -> pd.DataFrame:
    """
    Retorna dataframe com os dados atualizados do teste ABC.
    Mock: simula dados reais de segmentos de clientes.
    """
    df = pd.read_excel('dados.xlsx')
    df2 = df.copy()
    df2['qtd_pvs'] = df2['qtd_pvs'] + 10
    df2.to_excel('dados.xlsx', index=False)
    return df


def fill_data(update: int, rating_na: bool, rating_not_na: bool, df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra os dados do teste ABC.

    Args:
        update: após qual ajuste de preço filtrar (0 = todos)
        rating_na: incluir clientes sem rating
        rating_not_na: incluir clientes com rating
        df: dataframe com os dados brutos

    Returns:
        DataFrame com colunas: tipo_cluster, cluster, qtd_pvs, perf_a, perf_b, perf_c
    """
    df2 = df.copy()

    if update > 5:
        update = 5

    fator_rating = 0

    if rating_na:
        fator_rating += 1/3

    if rating_not_na:
        fator_rating += 2/3


    df2['qtd_pvs'] = df2['qtd_pvs'] * ((5-update) * 0.2) * fator_rating

    return df2


def get_policy() -> pd.DataFrame:
    """
    Retorna dataframe com a política de preços e incremento do teste.

    Returns:
        DataFrame com: tipo_cluster, cluster, inc_absoluto, inc_percentual, inc_teste
    """
    return pd.read_excel('politica.xlsx')


def to_json(df_policy: pd.DataFrame) -> str:
    """
    Serializa o dataframe de política com inc_teste atualizado para JSON.

    Args:
        df_policy: dataframe de política (possivelmente com ajustes aprovados)

    Returns:
        String JSON com a política atualizada
    """
    volumes = []
    prazos  = []
    ratings = []

    for _, r in df_policy.iterrows():
        item_a = {
            'CLUSTER': r['cluster'],
            'GRUPO_TESTE': 'A',
            'INC_PERC': r['inc_teste'] - 0.15
        }

        item_b = {
            'CLUSTER': r['cluster'],
            'GRUPO_TESTE': 'B',
            'INC_PERC': r['inc_teste']
        }

        item_c = {
            'CLUSTER': r['cluster'],
            'GRUPO_TESTE': 'C',
            'INC_PERC': r['inc_teste'] + 0.15
        }

        if r['tipo_cluster'] == 'volume':
            volumes.append(item_a)
            volumes.append(item_b)
            volumes.append(item_c)

        if r['tipo_cluster'] == 'prazo':
            prazos.append(item_a)
            prazos.append(item_b)
            prazos.append(item_c)

        if r['tipo_cluster'] == 'rating':
            ratings.append(item_a)
            ratings.append(item_b)
            ratings.append(item_c)

    json = {
        'VOLUME': volumes,
        'PRAZO': prazos,
        'RATING': ratings
    }

    return json
