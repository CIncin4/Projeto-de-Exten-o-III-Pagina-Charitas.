"""
SAP-Charitas | Consultas da tela publica de eventos (RF1).

So devolve dados que o visitante pode ver. O token_checkin (segredo do QR) NUNCA sai daqui.
"""

COLUNAS = ("id", "titulo", "descricao", "data_evento", "horario", "limite_vagas", "vagas_restantes")

# Eventos ativos de hoje em diante (data de hoje no fuso de Sao Paulo, nao do servidor).
# As vagas sao contadas no proprio SQL; LEFT JOIN para eventos sem inscritos tambem aparecerem.
_SQL = """
    SELECT e.id, e.titulo, e.descricao, e.data_evento, e.horario, e.limite_vagas,
           GREATEST(e.limite_vagas - count(a.id), 0) AS vagas_restantes
    FROM evento e
    LEFT JOIN agendamento a ON a.evento_id = e.id
    WHERE e.ativo = true
      AND e.data_evento >= (now() AT TIME ZONE 'America/Sao_Paulo')::date
      {filtro}
    GROUP BY e.id
    ORDER BY e.data_evento, e.horario
"""


def _para_dict(linha):
    return dict(zip(COLUNAS, linha))


def listar_eventos(conexao):
    """Lista de dicts, do evento mais proximo para o mais distante."""
    with conexao.cursor() as cur:
        cur.execute(_SQL.format(filtro=""))
        return [_para_dict(l) for l in cur.fetchall()]


def obter_evento(conexao, evento_id):
    """Um evento ativo e futuro, ou None (inexistente, desativado ou ja encerrado)."""
    with conexao.cursor() as cur:
        cur.execute(_SQL.format(filtro="AND e.id = %s"), (evento_id,))
        linha = cur.fetchone()
    return _para_dict(linha) if linha else None
