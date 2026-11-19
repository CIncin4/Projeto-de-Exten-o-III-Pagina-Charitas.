"""
SAP-Charitas | Aplicacao web (portal publico + painel do administrador).

Portal publico:
    GET  /                          -> redireciona para /eventos
    GET  /eventos                   -> lista de eventos com vagas (RF1)
    GET  /eventos/<id>/agendar      -> formulario de agendamento (RF2)
    POST /eventos/<id>/agendar      -> chama agendar() e mostra o resultado (RF2, RF7)
    GET  /eventos/<id>/confirmado   -> confirmacao do agendamento
    GET  /presenca/<token>          -> formulario de presenca do QR da entrada do museu (RF8)
    GET  /checkin/<token>           -> formulario de presenca do QR de um evento (RF8)
    POST (as duas acima)            -> grava a visita
    GET  /presenca-registrada       -> confirmacao da presenca

Painel do administrador (login obrigatorio): veja admin.py.

Rodar:  cd backend  &&  python app.py        (abre em http://localhost:5000)
"""
import logging
import os
import secrets
import traceback
from datetime import date, time, timedelta

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:      # so acontece em testes sem o pacote
    pass

from flask import Flask, redirect, render_template, request, url_for
from werkzeug.exceptions import HTTPException

import agendamento
import auth
import checkin
import db
import eventos
from admin import bp as admin_bp

app = Flask(__name__)

# ---------- configuracao ----------

_chave = os.getenv("SECRET_KEY")
if not _chave:
    # Sem SECRET_KEY o login funciona, mas cai a cada reinicio do servidor.
    logging.warning("SECRET_KEY nao definida no .env: usando uma chave temporaria.")
    _chave = secrets.token_hex(32)
app.secret_key = _chave
app.permanent_session_lifetime = timedelta(hours=8)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE") == "1",   # use COOKIE_SECURE=1 quando o site tiver HTTPS
    MAX_CONTENT_LENGTH=64 * 1024,                              # formularios pequenos: recusa corpos grandes
)
if os.getenv("TRUST_PROXY") == "1":     # atras de um proxy de hospedagem (Render, Railway...): enxerga o IP real
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

app.teardown_request(db.fechar_conexao)
app.jinja_env.globals["csrf_token"] = auth.csrf_token
app.register_blueprint(admin_bp)

conexao = db.get_conexao

DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
ESTADOS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR",
           "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]

# Envios por IP em 10 minutos (contra quem tenta lotar as vagas ou encher o dashboard de registros falsos).
# Folgados de proposito: varios visitantes na mesma rede Wi-Fi do museu compartilham o mesmo IP.
LIMITE_AGENDAR = (20, 600)
LIMITE_PRESENCA = (60, 600)

# Codigo devolvido por agendar() -> (mensagem para o visitante, status HTTP). RNF5: nada tecnico.
MENSAGENS = {
    "SEM_VAGAS": ("As vagas deste evento acabaram de esgotar. Veja outros eventos disponíveis.", 409),
    "JA_INSCRITO": ("Este e-mail já está inscrito neste evento.", 409),
    "DADOS_INVALIDOS": ("Confira os campos: nome, e-mail e telefone são obrigatórios.", 400),
}

# Codigo devolvido por registrar_visita() -> (mensagem, status HTTP)
MENSAGENS_PRESENCA = {
    "DADOS_INVALIDOS": ("Confira os campos: nome e cidade são obrigatórios.", 400),
    "JA_REGISTRADO": ("Você já registrou presença neste evento. Obrigado!", 409),
    "FORA_DA_JANELA": ("O registro de presença deste evento não está aberto agora.", 403),
}


# ---------- utilidades ----------

@app.template_filter("data_br")
def data_br(v):
    d = date.fromisoformat(v) if isinstance(v, str) else v
    return f"{DIAS[d.weekday()]}, {d.strftime('%d/%m/%Y')}"


@app.template_filter("hora_curta")
def hora_curta(v):
    t = time.fromisoformat(v) if isinstance(v, str) else v
    return t.strftime("%H:%M")


@app.after_request
def _cabecalhos(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    if request.path.startswith("/admin"):
        resp.headers["Cache-Control"] = "no-store"      # telas do painel nao ficam no cache do navegador
    return resp


def _muitas_tentativas():
    return render_template("erro.html", titulo="Muitas tentativas",
                           mensagem="Recebemos muitos envios deste endereço. Aguarde alguns minutos e tente de novo."), 429


def _nao_encontrado():
    return render_template(
        "erro.html", titulo="Evento não encontrado",
        mensagem="Este evento não existe ou já foi encerrado.",
    ), 404


@app.errorhandler(Exception)
def _erro_inesperado(exc):
    if isinstance(exc, HTTPException):          # 404 de rota, 405, 413 etc.
        titulo, msg = {
            400: ("Pedido inválido", "Não foi possível entender o que foi enviado."),
            413: ("Envio grande demais", "Os dados enviados são maiores que o permitido."),
            405: ("Ação não permitida", "Esta página não aceita essa ação."),
        }.get(exc.code, ("Página não encontrada", "Não encontramos o que você procurou."))
        return render_template("erro.html", titulo=titulo, mensagem=msg,
                               painel=request.path.startswith("/admin")), exc.code
    db.registrar_erro(f"portal {request.method} {request.path}", traceback.format_exc())
    return render_template(
        "erro.html", titulo="Algo deu errado",
        mensagem="Não foi possível concluir agora. Tente novamente em instantes.",
        painel=request.path.startswith("/admin"),
    ), 500


# ---------- eventos e agendamento (RF1, RF2, RF7) ----------

@app.get("/")
def inicio():
    return redirect(url_for("listar"))


@app.get("/eventos")
def listar():
    lista = eventos.listar_eventos(conexao())
    return render_template("eventos.html", eventos=lista)


@app.get("/eventos/<int:evento_id>/agendar")
def formulario(evento_id):
    evento = eventos.obter_evento(conexao(), evento_id)
    if evento is None:
        return _nao_encontrado()
    return render_template("agendar.html", evento=evento, dados={}, erro=None, limites=agendamento)


@app.post("/eventos/<int:evento_id>/agendar")
def enviar(evento_id):
    # Campo-isca escondido: so robo preenche. Finge sucesso e nao grava nada.
    if request.form.get("campo_extra"):
        return redirect(url_for("confirmado", evento_id=evento_id))
    if auth.excedeu_limite(f"agendar:{request.remote_addr}", *LIMITE_AGENDAR):
        return _muitas_tentativas()

    con = conexao()
    evento = eventos.obter_evento(con, evento_id)
    con.rollback()                               # encerra a leitura antes da transacao do agendar()
    if evento is None:
        return _nao_encontrado()

    dados = {c: request.form.get(c, "").strip() for c in ("nome", "email", "telefone")}
    codigo, _id = agendamento.agendar(con, evento_id, **dados)

    if codigo == "OK":                           # POST -> redirect -> GET: F5 nao reenvia
        return redirect(url_for("confirmado", evento_id=evento_id))
    if codigo == "EVENTO_INATIVO":
        return _nao_encontrado()
    erro, status = MENSAGENS[codigo]
    if codigo == "SEM_VAGAS":
        evento["vagas_restantes"] = 0
    return render_template("agendar.html", evento=evento, dados=dados, erro=erro, limites=agendamento), status


@app.get("/eventos/<int:evento_id>/confirmado")
def confirmado(evento_id):
    evento = eventos.obter_evento(conexao(), evento_id)   # None se o evento ja passou: tudo bem
    return render_template("confirmado.html", evento=evento)


# ---------- presenca por QR code (RF8) ----------

def _pagina_presenca(token, titulo, dados, erro, status=200):
    return render_template("presenca.html", token=token, evento_titulo=titulo, dados=dados, erro=erro,
                           estados=ESTADOS, max_nome=checkin.MAX_NOME, max_cidade=checkin.MAX_CIDADE,
                           max_email=checkin.MAX_EMAIL), status


@app.get("/presenca/<token>")
@app.get("/checkin/<token>")
def presenca_formulario(token):
    con = conexao()
    with con.cursor() as cur:
        codigo, titulo = checkin.consultar_qr(cur, token)
    con.rollback()
    if codigo == "QR_INVALIDO":
        return render_template("erro.html", titulo="QR code inválido",
                               mensagem="Este QR code não é válido. Peça ajuda à equipe da Casa de Cultura."), 404
    if codigo == "FORA_DA_JANELA":
        return render_template("erro.html", titulo="Presença fechada",
                               mensagem=MENSAGENS_PRESENCA["FORA_DA_JANELA"][0]), 403
    return _pagina_presenca(token, titulo, {}, None)


@app.post("/presenca/<token>")
@app.post("/checkin/<token>")
def presenca_enviar(token):
    if request.form.get("campo_extra"):              # isca para robos
        return redirect(url_for("presenca_registrada"))
    if auth.excedeu_limite(f"presenca:{request.remote_addr}", *LIMITE_PRESENCA):
        return _muitas_tentativas()
    dados = {c: request.form.get(c, "").strip() for c in ("nome", "cidade", "estado", "email")}
    con = conexao()
    with con.cursor() as cur:
        # primeiro o QR (invalido ou fora da janela vale mais que um campo vazio), depois os dados
        codigo, titulo = checkin.consultar_qr(cur, token)
        if codigo == "OK":
            codigo = checkin.registrar_visita(cur, token, dados["nome"], dados["cidade"],
                                              dados["estado"] or None, dados["email"] or None)
    if codigo == "OK":
        con.commit()
        return redirect(url_for("presenca_registrada"))
    con.rollback()
    if codigo == "QR_INVALIDO":
        return render_template("erro.html", titulo="QR code inválido",
                               mensagem="Este QR code não é válido. Peça ajuda à equipe da Casa de Cultura."), 404
    if codigo == "FORA_DA_JANELA":
        return render_template("erro.html", titulo="Presença fechada",
                               mensagem=MENSAGENS_PRESENCA["FORA_DA_JANELA"][0]), 403
    erro, status = MENSAGENS_PRESENCA[codigo]
    return _pagina_presenca(token, titulo, dados, erro, status)


@app.get("/presenca-registrada")
def presenca_registrada():
    return render_template("presenca_ok.html")


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1")
