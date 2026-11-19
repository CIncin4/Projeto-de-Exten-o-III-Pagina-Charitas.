"""
SAP-Charitas | Dados do painel do administrador: eventos (RF4) e lista de inscritos (RF5).

Todas as funcoes recebem um cursor; quem chama faz commit/rollback.
Excluir evento e LOGICO (ativo = false): o historico de inscricoes e presencas fica preservado.
"""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import checkin

FUSO = ZoneInfo("America/Sao_Paulo")
MAX_TITULO, MAX_DESCRICAO, MAX_VAGAS = 150, 2000, 1000


def validar_formulario(form, exigir_data_futura=True):
    """
    Confere os campos do formulario de evento.
    Retorna (dados, erros): dados com tipos Python (None se invalido), erros = lista de mensagens.
    """
    erros = []
    titulo = (form.get("titulo") or "").strip()
    descricao = (form.get("descricao") or "").strip()
    if "\x00" in titulo + descricao:
        titulo, descricao = "", ""
    if not titulo:
        erros.append("Informe o título do evento.")
    elif len(titulo) > MAX_TITULO:
        erros.append(f"O título pode ter até {MAX_TITULO} caracteres.")
    if len(descricao) > MAX_DESCRICAO:
        erros.append(f"A descrição pode ter até {MAX_DESCRICAO} caracteres.")

    data = hora = limite = None
    try:
        data = date.fromisoformat((form.get("data_evento") or "").strip())
        if not 2000 <= data.year <= 2100:
            raise ValueError
        if exigir_data_futura and data < datetime.now(FUSO).date():
            erros.append("A data do evento não pode ser anterior a hoje.")
    except ValueError:
        erros.append("Informe uma data válida.")
    try:
        hora = time.fromisoformat((form.get("horario") or "").strip()).replace(tzinfo=None, microsecond=0)
    except ValueError:
        erros.append("Informe um horário válido.")
    try:
        limite = int((form.get("limite_vagas") or "").strip())
        if not 1 <= limite <= MAX_VAGAS:
            raise ValueError
    except ValueError:
        limite = None
        erros.append(f"O limite de vagas deve ser um número de 1 a {MAX_VAGAS}.")

    dados = {"titulo": titulo, "descricao": descricao or None,
             "data_evento": data, "horario": hora, "limite_vagas": limite}
    return dados, erros


def _inicio(dados):
    return datetime.combine(dados["data_evento"], dados["horario"], tzinfo=FUSO)


def listar_todos(cur):
    """Todos os eventos (inclusive desativados) com total de inscritos e presentes."""
    cur.execute(
        """
        SELECT e.id, e.titulo, e.data_evento, e.horario, e.limite_vagas, e.ativo,
               count(a.id) AS inscritos,
               count(a.id) FILTER (WHERE a.presente) AS presentes
        FROM evento e
        LEFT JOIN agendamento a ON a.evento_id = e.id
        GROUP BY e.id
        ORDER BY e.data_evento DESC, e.horario DESC
        """
    )
    cols = ("id", "titulo", "data_evento", "horario", "limite_vagas", "ativo", "inscritos", "presentes")
    return [dict(zip(cols, l)) for l in cur.fetchall()]


def obter(cur, evento_id):
    cur.execute(
        """
        SELECT e.id, e.titulo, e.descricao, e.data_evento, e.horario, e.limite_vagas, e.ativo,
               e.token_checkin,
               to_char(e.checkin_abre_em AT TIME ZONE 'America/Sao_Paulo', 'DD/MM/YYYY HH24:MI'),
               to_char(e.checkin_fecha_em AT TIME ZONE 'America/Sao_Paulo', 'DD/MM/YYYY HH24:MI'),
               (SELECT count(*) FROM agendamento a WHERE a.evento_id = e.id),
               (SELECT count(*) FROM agendamento a WHERE a.evento_id = e.id AND a.presente)
        FROM evento e WHERE e.id = %s
        """,
        (evento_id,),
    )
    l = cur.fetchone()
    if l is None:
        return None
    cols = ("id", "titulo", "descricao", "data_evento", "horario", "limite_vagas", "ativo",
            "token_checkin", "janela_abre", "janela_fecha", "inscritos", "presentes")
    return dict(zip(cols, l))


def criar(cur, admin_id, dados):
    """Cria o evento com token de QR e janela de check-in padrao. Devolve (id, token)."""
    return checkin.criar_evento(cur, dados["titulo"], dados["descricao"], _inicio(dados),
                                dados["limite_vagas"], admin_id)


def atualizar(cur, evento_id, dados):
    """
    OK | NAO_ENCONTRADO | LIMITE_MENOR_QUE_INSCRITOS.
    A janela de check-in e recalculada a partir da nova data/horario (30 min antes ate 2 h depois).
    """
    cur.execute("SELECT id FROM evento WHERE id = %s FOR UPDATE", (evento_id,))
    if cur.fetchone() is None:
        return "NAO_ENCONTRADO"
    cur.execute("SELECT count(*) FROM agendamento WHERE evento_id = %s", (evento_id,))
    if dados["limite_vagas"] < cur.fetchone()[0]:
        return "LIMITE_MENOR_QUE_INSCRITOS"
    abre, fecha = checkin.janela_padrao(_inicio(dados))
    cur.execute(
        """
        UPDATE evento
        SET titulo = %s, descricao = %s, data_evento = %s, horario = %s, limite_vagas = %s,
            checkin_abre_em = %s, checkin_fecha_em = %s
        WHERE id = %s
        """,
        (dados["titulo"], dados["descricao"], dados["data_evento"], dados["horario"],
         dados["limite_vagas"], abre, fecha, evento_id),
    )
    return "OK"


def definir_ativo(cur, evento_id, ativo: bool) -> bool:
    """Exclusao logica (ativo=False) ou reativacao. False se o evento nao existe."""
    cur.execute("UPDATE evento SET ativo = %s WHERE id = %s RETURNING id", (ativo, evento_id))
    return cur.fetchone() is not None


def listar_inscritos(cur, evento_id):
    """Inscritos do evento (RF5) e, a parte, quem registrou presenca sem ter agendado (RF8)."""
    cur.execute(
        """
        SELECT id, nome, email, telefone, presente,
               to_char(checkin_em AT TIME ZONE 'America/Sao_Paulo', 'DD/MM HH24:MI'), checkin_metodo
        FROM agendamento WHERE evento_id = %s
        ORDER BY nome, id
        """,
        (evento_id,),
    )
    cols = ("id", "nome", "email", "telefone", "presente", "checkin_em", "checkin_metodo")
    inscritos = [dict(zip(cols, l)) for l in cur.fetchall()]
    cur.execute(
        """
        SELECT nome, cidade, to_char(registrada_em AT TIME ZONE 'America/Sao_Paulo', 'DD/MM HH24:MI')
        FROM visita WHERE evento_id = %s AND agendamento_id IS NULL
        ORDER BY registrada_em
        """,
        (evento_id,),
    )
    avulsos = [dict(zip(("nome", "cidade", "hora"), l)) for l in cur.fetchall()]
    return inscritos, avulsos


def evento_do_agendamento(cur, agendamento_id):
    cur.execute("SELECT evento_id FROM agendamento WHERE id = %s", (agendamento_id,))
    l = cur.fetchone()
    return l[0] if l else None
