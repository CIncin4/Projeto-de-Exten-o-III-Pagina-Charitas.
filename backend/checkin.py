"""
SAP-Charitas | Logica de check-in por QR code (exemplo independente de framework).

Usa psycopg2 (cursor padrao). Nao foi executado contra um banco real:
teste no seu PostgreSQL local antes de integrar.
"""
import secrets
from datetime import datetime, timedelta

# Janela padrao do check-in (o admin pode alterar ao criar/editar o evento)
ABRE_ANTES = timedelta(minutes=30)    # abre 30 min antes do horario do evento
FECHA_DEPOIS = timedelta(hours=2)     # fecha 2 h depois do horario do evento


def gerar_token() -> str:
    """Token aleatorio e imprevisivel (~22 caracteres) para o QR do evento."""
    return secrets.token_urlsafe(16)


def janela_padrao(inicio_evento: datetime) -> tuple[datetime, datetime]:
    """Calcula abertura e fechamento do check-in a partir do inicio do evento."""
    return inicio_evento - ABRE_ANTES, inicio_evento + FECHA_DEPOIS


def criar_evento(cur, titulo, descricao, inicio_evento, limite_vagas, admin_id):
    """inicio_evento: datetime com fuso (America/Sao_Paulo)."""
    abre, fecha = janela_padrao(inicio_evento)
    cur.execute(
        """
        INSERT INTO evento (titulo, descricao, data_evento, horario, limite_vagas,
                            token_checkin, checkin_abre_em, checkin_fecha_em, criado_por)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, token_checkin
        """,
        (titulo, descricao, inicio_evento.date(), inicio_evento.time(),
         limite_vagas, gerar_token(), abre, fecha, admin_id),
    )
    return cur.fetchone()


def renovar_token(cur, evento_id):
    """Se o QR vazar, o admin gera outro e o antigo para de funcionar."""
    novo = gerar_token()
    cur.execute("UPDATE evento SET token_checkin = %s WHERE id = %s", (novo, evento_id))
    return novo


def registrar_checkin_qr(cur, token: str, email: str) -> str:
    """
    Chamada pela pagina publica /checkin/<token>.
    Retorna um codigo de resultado; a tela traduz para mensagem amigavel
    (RNF5: nunca mostrar erro tecnico ao visitante).
    """
    # 1) token valido e evento ativo?
    cur.execute(
        """
        SELECT id, checkin_abre_em, checkin_fecha_em
        FROM evento
        WHERE token_checkin = %s AND ativo = true
        """,
        (token,),
    )
    evento = cur.fetchone()
    if evento is None:
        return "QR_INVALIDO"

    evento_id, abre, fecha = evento

    # 2) dentro da janela? (a hora vem do banco, nao do celular do visitante)
    cur.execute("SELECT now() BETWEEN %s AND %s", (abre, fecha))
    (dentro_da_janela,) = cur.fetchone()
    if not dentro_da_janela:
        return "FORA_DA_JANELA"

    # 3) marca presenca de forma atomica; so atualiza quem ainda nao fez check-in
    cur.execute(
        """
        UPDATE agendamento
        SET presente = true, checkin_em = now(), checkin_metodo = 'qrcode'
        WHERE evento_id = %s AND email = %s AND presente = false
        RETURNING id
        """,
        (evento_id, email.strip().lower()),
    )
    if cur.fetchone():
        return "OK"

    # 4) nao atualizou: ja fez check-in ou nao tem inscricao?
    cur.execute(
        "SELECT 1 FROM agendamento WHERE evento_id = %s AND email = %s",
        (evento_id, email.strip().lower()),
    )
    return "JA_REGISTRADO" if cur.fetchone() else "INSCRICAO_NAO_ENCONTRADA"


def marcar_presenca_manual(cur, agendamento_id, presente: bool):
    """Plano B (RF6): o admin marca ou desmarca no painel."""
    if presente:
        cur.execute(
            """
            UPDATE agendamento
            SET presente = true, checkin_em = now(), checkin_metodo = 'manual'
            WHERE id = %s
            """,
            (agendamento_id,),
        )
    else:
        cur.execute(
            """
            UPDATE agendamento
            SET presente = false, checkin_em = NULL, checkin_metodo = NULL
            WHERE id = %s
            """,
            (agendamento_id,),
        )


def gerar_qr_png(url_base: str, token: str, caminho_saida: str):
    """
    Gera a imagem do QR para o admin imprimir/exibir.
    Precisa do pacote 'qrcode[pil]' (pip install "qrcode[pil]").
    """
    import qrcode
    img = qrcode.make(f"{url_base}/checkin/{token}")
    img.save(caminho_saida)
