"""
SAP-Charitas | Portal publico do visitante (Sprint 2).

Rotas:
    GET  /                          -> redireciona para /eventos
    GET  /eventos                   -> lista de eventos com vagas (RF1)
    GET  /eventos/<id>/agendar      -> formulario de agendamento (RF2)
    POST /eventos/<id>/agendar      -> chama agendar() e mostra o resultado (RF2, RF7)
    GET  /eventos/<id>/confirmado   -> pagina de confirmacao

Rodar:  cd backend  &&  python app.py        (abre em http://localhost:5000)
"""
import os
import traceback
from datetime import date, time

from flask import Flask, g, redirect, render_template, request, url_for
from werkzeug.exceptions import HTTPException

import agendamento
import db
import eventos

app = Flask(__name__)

DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]

# Codigo devolvido por agendar() -> (mensagem para o visitante, status HTTP). RNF5: nada tecnico.
MENSAGENS = {
    "SEM_VAGAS": ("As vagas deste evento acabaram de esgotar. Veja outros eventos disponíveis.", 409),
    "JA_INSCRITO": ("Este e-mail já está inscrito neste evento.", 409),
    "DADOS_INVALIDOS": ("Confira os campos: nome, e-mail e telefone são obrigatórios.", 400),
}


# ---------- utilidades ----------

def conexao():
    """Uma conexao por requisicao, fechada sozinha no fim (teardown_request abaixo)."""
    if "con" not in g:
        g.con = db.conectar()
    return g.con


@app.teardown_request
def _fechar_conexao(_exc):
    con = g.pop("con", None)
    if con is not None:
        try:
            con.close()
        except Exception:
            pass


@app.template_filter("data_br")
def data_br(v):
    d = date.fromisoformat(v) if isinstance(v, str) else v
    return f"{DIAS[d.weekday()]}, {d.strftime('%d/%m/%Y')}"


@app.template_filter("hora_curta")
def hora_curta(v):
    t = time.fromisoformat(v) if isinstance(v, str) else v
    return t.strftime("%H:%M")


def _nao_encontrado():
    return render_template(
        "erro.html", titulo="Evento não encontrado",
        mensagem="Este evento não existe ou já foi encerrado.",
    ), 404


@app.errorhandler(Exception)
def _erro_inesperado(exc):
    if isinstance(exc, HTTPException):          # 404 de rota, 405 etc.
        return render_template("erro.html", titulo="Página não encontrada",
                               mensagem="Não encontramos o que você procurou."), exc.code
    db.registrar_erro(f"portal {request.method} {request.path}", traceback.format_exc())
    return render_template(
        "erro.html", titulo="Algo deu errado",
        mensagem="Não foi possível concluir agora. Tente novamente em instantes.",
    ), 500


# ---------- rotas ----------

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
    return render_template("agendar.html", evento=evento, dados={}, erro=None,
                           limites=agendamento)


@app.post("/eventos/<int:evento_id>/agendar")
def enviar(evento_id):
    # Campo-isca escondido: so robo preenche. Finge sucesso e nao grava nada.
    if request.form.get("website"):
        return redirect(url_for("confirmado", evento_id=evento_id))

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
    return render_template("agendar.html", evento=evento, dados=dados, erro=erro,
                           limites=agendamento), status


@app.get("/eventos/<int:evento_id>/confirmado")
def confirmado(evento_id):
    evento = eventos.obter_evento(conexao(), evento_id)   # None se o evento ja passou: tudo bem
    return render_template("confirmado.html", evento=evento)


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1")
