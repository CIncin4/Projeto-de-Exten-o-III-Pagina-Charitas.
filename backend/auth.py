"""
SAP-Charitas | Login do administrador (RF3, RNF1, RNF2).

* A senha NUNCA e guardada em texto: o banco usa bcrypt (extensao pgcrypto: crypt/gen_salt).
  Conferir e criar a senha acontece dentro do PostgreSQL, entao nao precisa de biblioteca extra.
* Sessao por cookie assinado (SECRET_KEY do .env), valido por 8 horas.
* Protecao contra CSRF nos formularios do painel e limite de tentativas de login.
"""
import hmac
import secrets
import time

from flask import session

MAX_FALHAS = 5                 # tentativas erradas ...
JANELA_FALHAS = 15 * 60        # ... em 15 minutos bloqueiam novas tentativas
MIN_SENHA, MAX_SENHA = 8, 72   # bcrypt so considera os 72 primeiros caracteres

# Hash valido de uma senha qualquer: usado para gastar o mesmo tempo quando o e-mail nao existe,
# para nao revelar (pelo tempo de resposta) quais e-mails sao de administradores.
_HASH_FALSO = "$2a$10$7K2dM68UN4UpFgdT7X0Dp.7z8wdOqrmVnG.Ds2dxuuQ7uGGUVks3W"

_falhas = {}                   # chave -> instantes das falhas (memoria do processo)


# ---------- limite de tentativas ----------

def _recentes(chave, agora):
    lista = [t for t in _falhas.get(chave, []) if agora - t < JANELA_FALHAS]
    if lista:
        _falhas[chave] = lista
    else:
        _falhas.pop(chave, None)
    return lista


def bloqueado(chaves) -> bool:
    agora = time.time()
    return any(len(_recentes(c, agora)) >= MAX_FALHAS for c in chaves)


def registrar_falha(chaves):
    agora = time.time()
    if len(_falhas) > 10000:   # evita crescer sem limite com e-mails inventados
        _falhas.clear()
    for c in chaves:
        _falhas.setdefault(c, []).append(agora)


def limpar_falhas(chaves):
    for c in chaves:
        _falhas.pop(c, None)


# ---------- limite de envios dos formularios publicos ----------

_contagem = {}                 # chave -> instantes dos envios (memoria do processo)


def excedeu_limite(chave, maximo, janela_s) -> bool:
    """True se a chave ja fez 'maximo' envios nos ultimos 'janela_s' segundos; senao registra este envio."""
    agora = time.time()
    if len(_contagem) > 10000:
        _contagem.clear()
    lista = [t for t in _contagem.get(chave, []) if agora - t < janela_s]
    if len(lista) >= maximo:
        _contagem[chave] = lista
        return True
    lista.append(agora)
    _contagem[chave] = lista
    return False


# ---------- credenciais ----------

def senha_valida_formato(senha) -> bool:
    return isinstance(senha, str) and 0 < len(senha) <= 200 and "\x00" not in senha


def verificar_login(cur, email, senha):
    """Devolve (id, nome) se e-mail e senha conferem; senao None."""
    if not email or not senha_valida_formato(senha) or "\x00" in email:
        return None
    cur.execute("SELECT id, nome, senha_hash FROM administrador WHERE email = %s", (email,))
    adm = cur.fetchone()
    cur.execute("SELECT crypt(%s, %s)", (senha, adm[2] if adm else _HASH_FALSO))
    calculado = cur.fetchone()[0]
    if adm and hmac.compare_digest(calculado.encode("utf-8"), adm[2].encode("utf-8")):
        return adm[0], adm[1]
    return None


def criar_admin(cur, nome, email, senha) -> str:
    """OK | EMAIL_EXISTE | DADOS_INVALIDOS. O chamador faz o commit."""
    nome = (nome or "").strip()
    email = (email or "").strip().lower()
    if (not nome or len(nome) > 100 or not email or len(email) > 150 or "@" not in email
            or "\x00" in nome + email or not isinstance(senha, str)
            or not (MIN_SENHA <= len(senha) <= MAX_SENHA) or "\x00" in senha):
        return "DADOS_INVALIDOS"
    cur.execute(
        """
        INSERT INTO administrador (nome, email, senha_hash)
        VALUES (%s, %s, crypt(%s, gen_salt('bf', 10)))
        ON CONFLICT (email) DO NOTHING
        RETURNING id
        """,
        (nome, email, senha),
    )
    return "OK" if cur.fetchone() else "EMAIL_EXISTE"


# ---------- sessao e CSRF ----------

def entrar(admin_id, nome):
    session.clear()                      # nova sessao a cada login (evita fixacao de sessao)
    session["admin_id"] = admin_id
    session["admin_nome"] = nome
    session["csrf"] = secrets.token_urlsafe(32)
    session.permanent = True


def sair():
    session.clear()


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def csrf_ok(formulario) -> bool:
    enviado = formulario.get("_csrf", "")
    esperado = session.get("csrf", "")
    # compare_digest com texto so aceita ASCII: compara em bytes para nao dar erro 500
    return bool(esperado) and hmac.compare_digest(enviado.encode("utf-8"), esperado.encode("utf-8"))
