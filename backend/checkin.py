"""
SAP-Charitas | Logica de presenca (formulario por QR code + marcacao manual).

Exemplo independente de framework, para usar com psycopg2 (cursor padrao).
Cada pessoa que registra presenca vira uma linha na tabela "visita" (migracao 001),
que alimenta o dashboard do administrador.

Dois tipos de QR code:
  * QR da entrada do museu: aponta para /presenca/<TOKEN_PRESENCA_GERAL>.
    Qualquer pessoa preenche, sem agendamento (visita geral).
  * QR de um evento: aponta para /checkin/<token_checkin do evento>.
    So funciona dentro da janela de check-in do evento.
"""
import os
import secrets
from datetime import datetime, timedelta

# Janela padrao do check-in (o admin pode alterar ao criar/editar o evento)
ABRE_ANTES = timedelta(minutes=30)    # abre 30 min antes do horario do evento
FECHA_DEPOIS = timedelta(hours=2)     # fecha 2 h depois do horario do evento

# Token do QR fixo da entrada do museu. Fica no .env, nunca no codigo.
# Gere um com: python -c "import secrets; print(secrets.token_urlsafe(16))"
TOKEN_GERAL_ENV = "TOKEN_PRESENCA_GERAL"

# Mesma regra do banco para nao estourar o tamanho das colunas
MAX_NOME, MAX_EMAIL, MAX_CIDADE = 100, 150, 100


def gerar_token() -> str:
    """Token aleatorio e imprevisivel (~22 caracteres) para o QR de um evento."""
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
    """Se o QR de um evento vazar, o admin gera outro e o antigo para de funcionar."""
    novo = gerar_token()
    cur.execute("UPDATE evento SET token_checkin = %s WHERE id = %s", (novo, evento_id))
    return novo


def _eh_token_geral(token: str) -> bool:
    geral = os.getenv(TOKEN_GERAL_ENV)
    return bool(geral) and bool(token) and secrets.compare_digest(token, geral)


def registrar_visita(cur, token, nome, cidade, estado=None, email=None) -> str:
    """
    Chamada pela pagina publica do formulario de presenca (RF8).
    Retorna um codigo de resultado; a tela traduz para mensagem amigavel
    (RNF5: nunca mostrar erro tecnico ao visitante).

    OK | QR_INVALIDO | FORA_DA_JANELA | JA_REGISTRADO | DADOS_INVALIDOS
    """
    nome = (nome or "").strip()
    cidade = (cidade or "").strip()
    estado = (estado or "").strip().upper() or None
    email = (email or "").strip().lower() or None

    if (not nome or not cidade
            or len(nome) > MAX_NOME or len(cidade) > MAX_CIDADE
            or (email and len(email) > MAX_EMAIL)
            or (estado and len(estado) != 2)):
        return "DADOS_INVALIDOS"

    # 1) de qual QR veio? Entrada do museu (sem evento) ou QR de um evento
    evento_id = None
    if not _eh_token_geral(token):
        # a hora vem do banco, nao do celular do visitante
        cur.execute(
            """
            SELECT id, now() BETWEEN checkin_abre_em AND checkin_fecha_em
            FROM evento
            WHERE token_checkin = %s AND ativo = true
            """,
            (token,),
        )
        evento = cur.fetchone()
        if evento is None:
            return "QR_INVALIDO"
        evento_id, dentro_da_janela = evento
        if not dentro_da_janela:
            return "FORA_DA_JANELA"

    # 2) a pessoa tinha agendado este evento? (so da para saber se informou o e-mail)
    agendamento_id = None
    if evento_id is not None and email:
        cur.execute(
            "SELECT id FROM agendamento WHERE evento_id = %s AND email = %s",
            (evento_id, email),
        )
        achou = cur.fetchone()
        if achou:
            agendamento_id = achou[0]

    # 3) grava a visita; o indice unico impede registrar duas vezes no mesmo evento
    cur.execute(
        """
        INSERT INTO visita (evento_id, agendamento_id, nome, email, cidade, estado, metodo)
        VALUES (%s, %s, %s, %s, %s, %s, 'qrcode')
        ON CONFLICT (evento_id, email) WHERE evento_id IS NOT NULL AND email IS NOT NULL
        DO NOTHING
        RETURNING id
        """,
        (evento_id, agendamento_id, nome, email, cidade, estado),
    )
    if cur.fetchone() is None:
        return "JA_REGISTRADO"

    # 4) se tinha agendamento, marca a presenca na lista do evento (RF5/RF6)
    if agendamento_id is not None:
        cur.execute(
            """
            UPDATE agendamento
            SET presente = true, checkin_em = now(), checkin_metodo = 'qrcode'
            WHERE id = %s AND presente = false
            """,
            (agendamento_id,),
        )
    return "OK"


def marcar_presenca_manual(cur, agendamento_id, presente: bool):
    """
    Plano B (RF6): o admin marca ou desmarca a presenca na lista do evento.
    A visita correspondente entra (ou sai) da tabela "visita", para o dashboard
    continuar batendo com a lista.
    """
    if presente:
        cur.execute(
            """
            UPDATE agendamento
            SET presente = true, checkin_em = now(), checkin_metodo = 'manual'
            WHERE id = %s AND presente = false
            RETURNING evento_id, nome, email
            """,
            (agendamento_id,),
        )
        linha = cur.fetchone()
        if linha:  # se ja estava presente, nao conta de novo
            evento_id, nome, email = linha
            cur.execute(
                """
                INSERT INTO visita (evento_id, agendamento_id, nome, email, metodo)
                VALUES (%s, %s, %s, %s, 'manual')
                ON CONFLICT (evento_id, email) WHERE evento_id IS NOT NULL AND email IS NOT NULL
                DO UPDATE SET agendamento_id = COALESCE(visita.agendamento_id, EXCLUDED.agendamento_id)
                """,
                (evento_id, agendamento_id, nome, email),
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
        cur.execute("DELETE FROM visita WHERE agendamento_id = %s", (agendamento_id,))


def gerar_qr_png(url_base: str, caminho: str, caminho_saida: str):
    """
    Gera a imagem do QR para o admin imprimir/exibir.
    caminho: "presenca/<TOKEN_PRESENCA_GERAL>" (entrada do museu) ou "checkin/<token_do_evento>".
    Precisa do pacote 'qrcode[pil]' (pip install "qrcode[pil]").
    """
    import qrcode
    img = qrcode.make(f"{url_base.rstrip('/')}/{caminho.lstrip('/')}")
    img.save(caminho_saida)
