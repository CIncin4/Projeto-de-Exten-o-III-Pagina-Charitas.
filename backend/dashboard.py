"""
SAP-Charitas | Estatisticas do dashboard do administrador (RF9).

Le a tabela "visita" e devolve SOMENTE dados agregados (RNF7): nenhum nome ou e-mail.
Os meses seguem o horario de Brasilia (uma visita as 22h de 31/10 conta em outubro).
"""
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
DIAS = ["domingo", "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado"]
SP = "America/Sao_Paulo"


def rotulo_mes(aaaa_mm: str) -> str:
    ano, mes = str(aaaa_mm).split("-")
    return f"{MESES[int(mes) - 1]}/{ano}"


def _barras(itens, chave="visitas"):
    """Acrescenta 'pct' (0-100) a cada item, relativo ao maior valor, para desenhar as barras."""
    maior = max([i[chave] for i in itens] + [1])
    for i in itens:
        i["pct"] = round(100 * i[chave] / maior)
    return itens


def estatisticas(cur):
    d = {}

    cur.execute("SELECT count(*) FROM visita")
    d["total"] = cur.fetchone()[0]

    # ultimos 12 meses, com 0 nos meses sem visita (o grafico nao "pula" meses)
    cur.execute(
        f"""
        WITH meses AS (
            SELECT generate_series(date_trunc('month', now() AT TIME ZONE '{SP}') - interval '11 months',
                                   date_trunc('month', now() AT TIME ZONE '{SP}'),
                                   interval '1 month') AS mes
        )
        SELECT to_char(m.mes, 'YYYY-MM'), count(v.id)
        FROM meses m
        LEFT JOIN visita v ON date_trunc('month', v.registrada_em AT TIME ZONE '{SP}') = m.mes
        GROUP BY m.mes
        ORDER BY m.mes
        """
    )
    d["por_mes"] = _barras([{"mes": l[0], "rotulo": rotulo_mes(l[0]), "visitas": l[1]} for l in cur.fetchall()])
    d["mes_atual"] = d["por_mes"][-1]["visitas"] if d["por_mes"] else 0

    # mes com mais visitas, em todo o historico
    cur.execute(
        f"""
        SELECT to_char(date_trunc('month', registrada_em AT TIME ZONE '{SP}'), 'YYYY-MM') AS mes, count(*) AS visitas
        FROM visita GROUP BY mes ORDER BY visitas DESC, mes DESC LIMIT 1
        """
    )
    l = cur.fetchone()
    d["mes_top"] = {"rotulo": rotulo_mes(l[0]), "visitas": l[1]} if l else None

    cur.execute(
        """
        SELECT min(btrim(cidade)), estado, count(*) AS visitas
        FROM visita WHERE cidade IS NOT NULL AND btrim(cidade) <> ''
        GROUP BY lower(btrim(cidade)), estado ORDER BY visitas DESC, lower(btrim(cidade)) LIMIT 10
        """
    )
    d["cidades"] = _barras([{"cidade": l[0], "estado": l[1], "visitas": l[2]} for l in cur.fetchall()])

    cur.execute(
        """
        SELECT COALESCE(e.titulo, 'Visita geral') AS origem, count(*) AS visitas
        FROM visita v LEFT JOIN evento e ON e.id = v.evento_id
        GROUP BY v.evento_id, e.titulo ORDER BY visitas DESC, origem
        """
    )
    d["por_evento"] = _barras([{"origem": l[0], "visitas": l[1]} for l in cur.fetchall()])

    cur.execute(
        """
        SELECT e.titulo, count(a.id) AS agendados, count(a.id) FILTER (WHERE a.presente) AS presentes
        FROM evento e LEFT JOIN agendamento a ON a.evento_id = e.id
        WHERE e.ativo GROUP BY e.id, e.titulo, e.data_evento
        ORDER BY e.data_evento
        """
    )
    comp = []
    for titulo, agendados, presentes in cur.fetchall():
        taxa = round(100 * presentes / agendados) if agendados else None
        comp.append({"titulo": titulo, "agendados": agendados, "presentes": presentes, "taxa": taxa})
    d["comparecimento"] = comp

    cur.execute(
        f"""
        SELECT EXTRACT(DOW FROM registrada_em AT TIME ZONE '{SP}')::int AS dia, count(*) AS visitas
        FROM visita GROUP BY dia ORDER BY visitas DESC, dia
        """
    )
    d["dias"] = _barras([{"dia": DIAS[l[0]], "visitas": l[1]} for l in cur.fetchall()])

    cur.execute("SELECT metodo, count(*) FROM visita GROUP BY metodo ORDER BY metodo")
    nomes = {"qrcode": "QR code", "manual": "Marcada pelo administrador"}
    d["metodos"] = _barras([{"metodo": nomes.get(l[0], l[0]), "visitas": l[1]} for l in cur.fetchall()])
    return d
