"""
SAP-Charitas | Agendamento com limite de vagas (RF2 e RF7).

Exemplo para psycopg2. Recebe a CONEXAO (nao o cursor) porque a funcao controla a
transacao: o evento fica travado ate o commit/rollback, e e isso que impede duas
inscricoes simultaneas de passarem do limite de vagas.

Precisa de uma conexao em modo padrao do psycopg2 (autocommit desligado).
"""

MAX_NOME, MAX_EMAIL, MAX_TELEFONE = 100, 150, 20


def agendar(conexao, evento_id, nome, email, telefone):
    """
    Inscreve um visitante em um evento, respeitando o limite de vagas.

    Retorna (codigo, agendamento_id):
        ("OK", id)               inscricao gravada
        ("SEM_VAGAS", None)      o evento esta lotado
        ("JA_INSCRITO", None)    este e-mail ja esta inscrito neste evento
        ("EVENTO_INATIVO", None) o evento nao existe ou foi desativado
        ("DADOS_INVALIDOS", None) campo vazio ou grande demais
    A tela traduz o codigo para uma mensagem amigavel (RNF5).
    """
    nome = (nome or "").strip()
    email = (email or "").strip().lower()      # sempre em minusculas (ver schema.sql)
    telefone = (telefone or "").strip()
    if (not nome or not email or not telefone
            or len(nome) > MAX_NOME or len(email) > MAX_EMAIL or len(telefone) > MAX_TELEFONE):
        return "DADOS_INVALIDOS", None

    try:
        with conexao.cursor() as cur:
            # 1) Trava a linha do evento. Quem chegar ao mesmo tempo espera aqui ate a
            #    transacao anterior terminar; so entao conta as vagas de novo.
            cur.execute(
                "SELECT limite_vagas FROM evento WHERE id = %s AND ativo = true FOR UPDATE",
                (evento_id,),
            )
            evento = cur.fetchone()
            if evento is None:
                conexao.rollback()
                return "EVENTO_INATIVO", None
            (limite,) = evento

            # 2) Ja esta inscrito? (antes de contar, para quem repete nao ver "sem vagas")
            cur.execute(
                "SELECT 1 FROM agendamento WHERE evento_id = %s AND email = %s",
                (evento_id, email),
            )
            if cur.fetchone():
                conexao.rollback()
                return "JA_INSCRITO", None

            # 3) Ainda ha vaga?
            cur.execute("SELECT count(*) FROM agendamento WHERE evento_id = %s", (evento_id,))
            (inscritos,) = cur.fetchone()
            if inscritos >= limite:
                conexao.rollback()
                return "SEM_VAGAS", None

            # 4) Grava. O UNIQUE (evento_id, email) do banco e a rede de seguranca final.
            cur.execute(
                """
                INSERT INTO agendamento (evento_id, nome, email, telefone)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (evento_id, email) DO NOTHING
                RETURNING id
                """,
                (evento_id, nome, email, telefone),
            )
            novo = cur.fetchone()
            if novo is None:
                conexao.rollback()
                return "JA_INSCRITO", None

        conexao.commit()
        return "OK", novo[0]
    except Exception:
        conexao.rollback()   # falha tecnica: desfaz tudo e deixa o erro subir (vai para o log_erro, RNF4)
        raise
