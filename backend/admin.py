"""
SAP-Charitas | Rotas do painel do administrador (area restrita, prefixo /admin).

    /admin/login, /admin/logout            login e saida (RF3)
    /admin/eventos ...                     CRUD de eventos (RF4)
    /admin/eventos/<id>/inscritos          lista de inscritos (RF5) e marcar presenca (RF6)
    /admin/dashboard                       estatisticas das visitas (RF9)
    /admin/qr                              QR codes para imprimir

Todas as rotas, menos o login, exigem sessao de administrador; todo POST exige o token CSRF.
"""
import os

from flask import (Blueprint, Response, abort, flash, redirect, render_template, request,
                   session, url_for)

import admin_eventos
import auth
import checkin
import dashboard
import db
import qr

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _con():
    return db.get_conexao()


def _erro(titulo, mensagem, status):
    return render_template("erro.html", titulo=titulo, mensagem=mensagem, painel=True), status


@bp.before_request
def _protecao():
    """Login obrigatorio (com checagem de que o administrador ainda existe) e CSRF em todo POST."""
    if request.endpoint != "admin.login":
        if "admin_id" not in session:
            return redirect(url_for("admin.login"))
        con = _con()
        with con.cursor() as cur:
            cur.execute("SELECT 1 FROM administrador WHERE id = %s", (session["admin_id"],))
            existe = cur.fetchone() is not None
        con.rollback()
        if not existe:
            auth.sair()
            return redirect(url_for("admin.login"))
    if request.method == "POST" and not auth.csrf_ok(request.form):
        if request.endpoint == "admin.login":
            return _login_pagina("Sua sessão expirou. Tente entrar de novo.", "", 400)
        return _erro("Sessão expirada", "Não foi possível confirmar a ação. Recarregue a página e tente de novo.", 400)
    return None


# ---------- login e saida ----------

def _login_pagina(erro, email, status=200):
    return render_template("admin/login.html", erro=erro, email=email), status


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if "admin_id" in session:
            return redirect(url_for("admin.eventos"))
        return _login_pagina(None, "")

    email = (request.form.get("email") or "").strip().lower()
    senha = request.form.get("senha") or ""
    chaves = [f"ip:{request.remote_addr}", f"email:{email}"]
    if auth.bloqueado(chaves):
        return _login_pagina("Muitas tentativas. Aguarde alguns minutos e tente de novo.", email, 429)
    con = _con()
    with con.cursor() as cur:
        adm = auth.verificar_login(cur, email, senha)
    con.rollback()
    if adm is None:
        auth.registrar_falha(chaves)
        return _login_pagina("E-mail ou senha incorretos.", email, 401)
    auth.limpar_falhas(chaves)
    auth.entrar(*adm)
    return redirect(url_for("admin.eventos"))


@bp.post("/logout")
def logout():
    auth.sair()
    return redirect(url_for("admin.login"))


@bp.get("/")
def inicio():
    return redirect(url_for("admin.eventos"))


# ---------- eventos (RF4) ----------

@bp.get("/eventos")
def eventos():
    con = _con()
    with con.cursor() as cur:
        lista = admin_eventos.listar_todos(cur)
    return render_template("admin/eventos.html", eventos=lista)


@bp.route("/eventos/novo", methods=["GET", "POST"])
def evento_novo():
    valores, erros = {}, []
    if request.method == "POST":
        valores = request.form
        dados, erros = admin_eventos.validar_formulario(request.form)
        if not erros:
            con = _con()
            with con.cursor() as cur:
                admin_eventos.criar(cur, session["admin_id"], dados)
            con.commit()
            flash("Evento criado. O QR code do check-in já está disponível na lista de inscritos.")
            return redirect(url_for("admin.eventos"))
    return render_template("admin/evento_form.html", evento=None, valores=valores, erros=erros,
                           maximos=admin_eventos), (400 if erros else 200)


@bp.route("/eventos/<int:evento_id>/editar", methods=["GET", "POST"])
def evento_editar(evento_id):
    con = _con()
    with con.cursor() as cur:
        evento = admin_eventos.obter(cur, evento_id)
    con.rollback()
    if evento is None:
        return _erro("Evento não encontrado", "Este evento não existe.", 404)
    if request.method == "GET":
        valores = {"titulo": evento["titulo"], "descricao": evento["descricao"] or "",
                   "data_evento": str(evento["data_evento"]), "horario": str(evento["horario"])[:5],
                   "limite_vagas": evento["limite_vagas"]}
        return render_template("admin/evento_form.html", evento=evento, valores=valores, erros=[],
                               maximos=admin_eventos)
    # ao editar, a data pode ficar no passado (corrigir um evento que ja aconteceu)
    dados, erros = admin_eventos.validar_formulario(request.form, exigir_data_futura=False)
    if not erros:
        with con.cursor() as cur:
            codigo = admin_eventos.atualizar(cur, evento_id, dados)
        if codigo == "OK":
            con.commit()
            flash("Evento atualizado.")
            return redirect(url_for("admin.eventos"))
        con.rollback()
        erros = ["Este evento não existe."] if codigo == "NAO_ENCONTRADO" else [
            f"O evento já tem {evento['inscritos']} inscritos: o limite de vagas não pode ser menor que isso."]
    return render_template("admin/evento_form.html", evento=evento, valores=request.form, erros=erros,
                           maximos=admin_eventos), 400


def _definir_ativo(evento_id, ativo, mensagem):
    con = _con()
    with con.cursor() as cur:
        achou = admin_eventos.definir_ativo(cur, evento_id, ativo)
    if not achou:
        con.rollback()
        return _erro("Evento não encontrado", "Este evento não existe.", 404)
    con.commit()
    flash(mensagem)
    return redirect(url_for("admin.eventos"))


@bp.post("/eventos/<int:evento_id>/excluir")
def evento_excluir(evento_id):
    return _definir_ativo(evento_id, False,
                          "Evento excluído da página pública. O histórico de inscrições foi mantido.")


@bp.post("/eventos/<int:evento_id>/reativar")
def evento_reativar(evento_id):
    return _definir_ativo(evento_id, True, "Evento reativado.")


@bp.post("/eventos/<int:evento_id>/renovar-qr")
def evento_renovar_qr(evento_id):
    con = _con()
    with con.cursor() as cur:
        if admin_eventos.obter(cur, evento_id) is None:
            con.rollback()
            return _erro("Evento não encontrado", "Este evento não existe.", 404)
        checkin.renovar_token(cur, evento_id)
    con.commit()
    flash("Novo QR code gerado. O QR antigo deixou de funcionar.")
    return redirect(url_for("admin.inscritos", evento_id=evento_id))


# ---------- inscritos e presenca (RF5, RF6) ----------

@bp.get("/eventos/<int:evento_id>/inscritos")
def inscritos(evento_id):
    con = _con()
    with con.cursor() as cur:
        evento = admin_eventos.obter(cur, evento_id)
        if evento is None:
            return _erro("Evento não encontrado", "Este evento não existe.", 404)
        lista, avulsos = admin_eventos.listar_inscritos(cur, evento_id)
    con.rollback()
    return render_template("admin/inscritos.html", evento=evento, inscritos=lista, avulsos=avulsos,
                           url_qr=f"{qr.base_url(request)}/checkin/{evento['token_checkin']}")


@bp.post("/inscritos/<int:agendamento_id>/presenca")
def presenca(agendamento_id):
    presente = request.form.get("presente") == "1"
    con = _con()
    with con.cursor() as cur:
        evento_id = admin_eventos.evento_do_agendamento(cur, agendamento_id)
        if evento_id is None:
            con.rollback()
            return _erro("Inscrição não encontrada", "Esta inscrição não existe.", 404)
        checkin.marcar_presenca_manual(cur, agendamento_id, presente)
    con.commit()
    return redirect(url_for("admin.inscritos", evento_id=evento_id))


# ---------- dashboard (RF9) ----------

@bp.get("/dashboard")
def dashboard_pagina():
    con = _con()
    with con.cursor() as cur:
        dados = dashboard.estatisticas(cur)
    con.rollback()
    return render_template("admin/dashboard.html", d=dados)


# ---------- QR codes ----------

def _png(url):
    try:
        conteudo = qr.png_bytes(url)
    except ImportError:
        return _erro("QR code indisponível", "Instale o pacote qrcode[pil] (pip install -r requirements.txt).", 500)
    return Response(conteudo, mimetype="image/png", headers={"Cache-Control": "no-store"})


@bp.get("/eventos/<int:evento_id>/qr.png")
def qr_evento(evento_id):
    con = _con()
    with con.cursor() as cur:
        evento = admin_eventos.obter(cur, evento_id)
    con.rollback()
    if evento is None:
        abort(404)
    return _png(f"{qr.base_url(request)}/checkin/{evento['token_checkin']}")


@bp.get("/qr-entrada.png")
def qr_entrada():
    token = os.getenv(checkin.TOKEN_GERAL_ENV)
    if not token:
        abort(404)
    return _png(f"{qr.base_url(request)}/presenca/{token}")


@bp.get("/qr")
def qr_pagina():
    token = os.getenv(checkin.TOKEN_GERAL_ENV)
    return render_template("admin/qr.html", configurado=bool(token),
                           url=f"{qr.base_url(request)}/presenca/{token}" if token else None)
