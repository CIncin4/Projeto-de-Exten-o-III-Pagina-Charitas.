"""
SAP-Charitas | Teste do painel do administrador e da presenca por QR contra o banco real.

Cobre: login (RF3), CRUD de eventos (RF4), lista de inscritos (RF5), presenca manual (RF6),
formulario de presenca por QR (RF8) e dashboard (RF9), alem de protecoes (CSRF, sessao, limites).
Usa o cliente de teste do Flask. Cria um administrador e eventos de teste e apaga tudo no final.

Rodar (com o .venv ativo e o .env configurado):   python testar_admin.py
"""
import os
import sys
import types
from datetime import datetime, timedelta

import db

EMAIL = "teste-admin@exemplo.com"
SENHA = "senha-de-teste-123"
PREFIXO = "[TESTE] admin"
NOME_TESTE = "[TESTE-ADM] "
TOKEN_GERAL = "token-geral-do-teste-admin"
falhas = 0


def confere(nome, condicao, detalhe=""):
    global falhas
    falhas += 0 if condicao else 1
    print("OK    " if condicao else "FALHOU", nome, "" if condicao else f"-> {detalhe}")


def _sql(conectar, sql, params=(), ler=False):
    con = conectar()
    try:
        with con.cursor() as cur:
            cur.execute(sql, params)
            r = cur.fetchall() if ler else None
        con.commit()
        return r
    finally:
        con.close()


def _um(conectar, sql, params=()):
    return _sql(conectar, sql, params, ler=True)[0][0]


def _limpar(conectar):
    _sql(conectar, "DELETE FROM visita WHERE nome LIKE %s", (NOME_TESTE + "%",))
    _sql(conectar, "DELETE FROM visita WHERE evento_id IN (SELECT id FROM evento WHERE titulo LIKE %s)", (PREFIXO + "%",))
    _sql(conectar, "DELETE FROM agendamento WHERE evento_id IN (SELECT id FROM evento WHERE titulo LIKE %s)", (PREFIXO + "%",))
    _sql(conectar, "DELETE FROM visita WHERE evento_id IN (SELECT id FROM evento WHERE criado_por IN (SELECT id FROM administrador WHERE email = %s))", (EMAIL,))
    _sql(conectar, "DELETE FROM agendamento WHERE evento_id IN (SELECT id FROM evento WHERE criado_por IN (SELECT id FROM administrador WHERE email = %s))", (EMAIL,))
    _sql(conectar, "DELETE FROM evento WHERE criado_por IN (SELECT id FROM administrador WHERE email = %s)", (EMAIL,))
    _sql(conectar, "DELETE FROM evento WHERE titulo LIKE %s", (PREFIXO + "%",))
    _sql(conectar, "DELETE FROM administrador WHERE email = %s", (EMAIL,))
    _sql(conectar, "DELETE FROM log_erro WHERE mensagem LIKE %s", ("%TESTE-ADMIN%",))


def _evento_sql(conectar, sufixo, dias, limite, janela_aberta=False):
    """Evento direto no banco. janela_aberta: check-in aberto agora (para testar o QR)."""
    abre = "now() - interval '1 hour'" if janela_aberta else "now() + interval '10 days'"
    fecha = "now() + interval '1 hour'" if janela_aberta else "now() + interval '11 days'"
    return _sql(conectar, f"""
        INSERT INTO evento (titulo, descricao, data_evento, horario, limite_vagas, token_checkin,
                            checkin_abre_em, checkin_fecha_em)
        VALUES (%s, 'desc', (now() AT TIME ZONE 'America/Sao_Paulo')::date + %s, '10:00', %s, %s, {abre}, {fecha})
        RETURNING id, token_checkin""", (f"{PREFIXO} {sufixo}", dias, limite, "tok-" + sufixo.replace(" ", "-") + "-" + str(abs(hash(sufixo)) % 99999)), ler=True)[0]


def rodar(conectar):
    db.conectar = conectar
    os.environ["TOKEN_PRESENCA_GERAL"] = TOKEN_GERAL
    os.environ.setdefault("APP_BASE_URL", "http://teste.local")
    try:
        import qrcode  # noqa: F401
        qr_real = True
    except ImportError:                        # sem o pacote: usa um falso so para testar a rota
        qr_real = False
        falso = types.ModuleType("qrcode")
        class _Img:
            def save(self, buf, format="PNG"):
                buf.write(b"\x89PNG\r\n\x1a\nfalso")
        falso.make = lambda url: _Img()
        sys.modules["qrcode"] = falso

    import admin_eventos
    import agendamento
    import checkin
    import app as portal
    import auth

    app = portal.app
    cliente = app.test_client()
    _limpar(conectar)

    def csrf():
        with cliente.session_transaction() as s:
            return s.get("csrf", "")

    def post(url, dados=None, com_csrf=True, c=None):
        c = c or cliente
        dados = dict(dados or {})
        if com_csrf:
            with c.session_transaction() as s:
                dados["_csrf"] = s.get("csrf", "")
        return c.post(url, data=dados)

    def html(r):
        return r.get_data(as_text=True)

    amanha = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    form_ok = {"titulo": f"{PREFIXO} criado", "descricao": "texto", "data_evento": amanha,
               "horario": "14:30", "limite_vagas": "5"}

    try:
        con = conectar()
        with con.cursor() as cur:
            codigo = auth.criar_admin(cur, "Admin Teste", EMAIL, SENHA)
        con.commit(); con.close()
        confere("cria administrador de teste (senha com bcrypt)", codigo == "OK", codigo)
        h = _um(conectar, "SELECT senha_hash FROM administrador WHERE email = %s", (EMAIL,))
        confere("  senha NAO ficou em texto no banco", SENHA not in h and h.startswith("$2"), h[:10])
        con = conectar()
        with con.cursor() as cur:
            confere("  e-mail repetido e recusado", auth.criar_admin(cur, "Outro", EMAIL.upper(), SENHA) == "EMAIL_EXISTE")
            confere("  senha curta e recusada", auth.criar_admin(cur, "Outro", "outro@exemplo.com", "123") == "DADOS_INVALIDOS")
        con.rollback(); con.close()

        print("== Sem login")
        for metodo, url in [("get", "/admin/eventos"), ("get", "/admin/dashboard"), ("get", "/admin/qr"),
                            ("get", "/admin/eventos/1/inscritos"), ("get", "/admin/eventos/1/qr.png"),
                            ("get", "/admin/qr-entrada.png"), ("post", "/admin/eventos/novo"),
                            ("post", "/admin/eventos/1/excluir"), ("post", "/admin/inscritos/1/presenca")]:
            r = getattr(cliente, metodo)(url)
            confere(f"{metodo.upper()} {url} -> redireciona ao login",
                    r.status_code == 302 and "/admin/login" in r.headers["Location"], r.status_code)

        print("== Login")
        r = cliente.get("/admin/login")
        confere("GET login -> 200 com token CSRF", r.status_code == 200 and 'name="_csrf"' in html(r))
        confere("  cookie de sessao HttpOnly e SameSite", "HttpOnly" in r.headers.get("Set-Cookie", "") and "SameSite=Lax" in r.headers.get("Set-Cookie", ""),
                r.headers.get("Set-Cookie"))
        r = post("/admin/login", {"email": EMAIL, "senha": SENHA}, com_csrf=False)
        confere("POST sem CSRF -> 400", r.status_code == 400, r.status_code)
        r = post("/admin/login", {"email": EMAIL, "senha": "errada"})
        confere("senha errada -> 401", r.status_code == 401 and "incorretos" in html(r), r.status_code)
        r2 = post("/admin/login", {"email": "naoexiste@exemplo.com", "senha": "qualquer"})
        confere("e-mail inexistente -> mesma resposta 401", r2.status_code == 401 and "incorretos" in html(r2))
        confere("  mensagem identica (nao revela se o e-mail existe)", html(r).split("incorretos")[0][-60:] == html(r2).split("incorretos")[0][-60:])
        r = post("/admin/login", {"email": EMAIL, "senha": "a\x00b"})
        confere("senha com caractere nulo -> 401 (nao quebra)", r.status_code == 401, r.status_code)
        r = post("/admin/login", {"email": "' OR '1'='1", "senha": "' OR '1'='1"})
        confere("tentativa de SQL injection -> 401", r.status_code == 401, r.status_code)
        r = cliente.get("/admin/eventos")
        confere("continua sem acesso apos falhas", r.status_code == 302)

        auth._falhas.clear()
        for _ in range(auth.MAX_FALHAS):
            post("/admin/login", {"email": "alvo@exemplo.com", "senha": "x"})
        r = post("/admin/login", {"email": "alvo@exemplo.com", "senha": "x"})
        confere("apos 5 erros -> 429 (bloqueio temporario)", r.status_code == 429, r.status_code)
        auth._falhas.clear()

        r = post("/admin/login", {"email": EMAIL.upper(), "senha": SENHA})
        confere("login correto -> redireciona ao painel", r.status_code == 302 and r.headers["Location"].endswith("/admin/eventos"), r.status_code)
        r = cliente.get("/admin/eventos")
        confere("painel abre logado", r.status_code == 200 and "Novo evento" in html(r))
        confere("  cabecalhos de seguranca", r.headers.get("X-Frame-Options") == "DENY" and r.headers.get("Cache-Control") == "no-store"
                and r.headers.get("X-Content-Type-Options") == "nosniff")

        print("== Eventos (RF4)")
        r = post("/admin/eventos/novo", form_ok, com_csrf=False)
        confere("criar sem CSRF -> 400 e nada criado", r.status_code == 400 and _um(conectar, "SELECT count(*) FROM evento WHERE titulo = %s", (form_ok["titulo"],)) == 0)
        ruins = [({**form_ok, "titulo": "  "}, "título"), ({**form_ok, "data_evento": "2020-01-01"}, "anterior a hoje"),
                 ({**form_ok, "data_evento": "31/12/2026"}, "data válida"), ({**form_ok, "horario": "25:99"}, "horário válido"),
                 ({**form_ok, "limite_vagas": "0"}, "1 a"), ({**form_ok, "limite_vagas": "abc"}, "1 a"),
                 ({**form_ok, "limite_vagas": "99999"}, "1 a"), ({**form_ok, "titulo": "x" * 151}, "150")]
        for dados, trecho in ruins:
            r = post("/admin/eventos/novo", dados)
            confere(f"dado invalido ({trecho}) -> 400 com mensagem", r.status_code == 400 and trecho in html(r), r.status_code)
        confere("  nenhum evento invalido foi criado", _um(conectar, "SELECT count(*) FROM evento WHERE titulo LIKE %s", (PREFIXO + " criado%",)) == 0)
        r = post("/admin/eventos/novo", {**form_ok, "titulo": "<script>alert(1)</script>", "limite_vagas": "0"})
        confere("titulo com HTML e escapado ao reexibir o formulario", r.status_code == 400 and "<script>alert(1)</script>" not in html(r) and "&lt;script&gt;" in html(r))

        r = post("/admin/eventos/novo", form_ok)
        confere("criar evento valido -> 302", r.status_code == 302, r.status_code)
        ev = _sql(conectar, "SELECT id, limite_vagas, ativo, criado_por, length(token_checkin) FROM evento WHERE titulo = %s", (form_ok["titulo"],), ler=True)
        confere("  gravou com token de QR e administrador criador", len(ev) == 1 and ev[0][1] == 5 and ev[0][2] is True and ev[0][3] and ev[0][4] >= 20, ev)
        eid = ev[0][0]
        ok_janela = _um(conectar, "SELECT checkin_abre_em = ((data_evento + horario) AT TIME ZONE 'America/Sao_Paulo') - interval '30 minutes' "
                                  "AND checkin_fecha_em = ((data_evento + horario) AT TIME ZONE 'America/Sao_Paulo') + interval '2 hours' FROM evento WHERE id = %s", (eid,))
        confere("  janela de check-in: 30 min antes ate 2 h depois (horario de Brasilia)", ok_janela is True, ok_janela)
        confere("  evento aparece na pagina publica", form_ok["titulo"] in html(cliente.get("/eventos")))

        r = cliente.get(f"/admin/eventos/{eid}/editar")
        confere("editar: formulario vem preenchido", r.status_code == 200 and form_ok["titulo"] in html(r) and 'value="14:30"' in html(r))
        r = post(f"/admin/eventos/{eid}/editar", {**form_ok, "titulo": f"{PREFIXO} editado", "horario": "09:00", "limite_vagas": "2"})
        confere("editar -> 302", r.status_code == 302, r.status_code)
        ok_janela = _um(conectar, "SELECT titulo = %s AND limite_vagas = 2 AND checkin_abre_em = ((data_evento + horario) AT TIME ZONE 'America/Sao_Paulo') - interval '30 minutes' "
                                  "AND horario = '09:00' FROM evento WHERE id = %s", (f"{PREFIXO} editado", eid))
        confere("  campos atualizados e janela recalculada", ok_janela is True, ok_janela)
        con = conectar()
        agendamento.agendar(con, eid, "Pessoa Um", "um@exemplo.com", "22999990001")
        agendamento.agendar(con, eid, "Pessoa Dois", "dois@exemplo.com", "22999990002")
        con.close()
        r = post(f"/admin/eventos/{eid}/editar", {**form_ok, "titulo": f"{PREFIXO} editado", "limite_vagas": "1"})
        confere("reduzir vagas abaixo dos inscritos -> 400", r.status_code == 400 and "2 inscritos" in html(r), r.status_code)
        confere("  limite continua 2", _um(conectar, "SELECT limite_vagas FROM evento WHERE id = %s", (eid,)) == 2)
        r = post("/admin/eventos/999999/editar", form_ok)
        confere("editar evento inexistente -> 404", r.status_code == 404, r.status_code)

        r = post(f"/admin/eventos/{eid}/excluir", com_csrf=False)
        confere("excluir sem CSRF -> 400 e continua ativo", r.status_code == 400 and _um(conectar, "SELECT ativo FROM evento WHERE id = %s", (eid,)) is True)
        r = post(f"/admin/eventos/{eid}/excluir")
        confere("excluir -> 302 (exclusao logica)", r.status_code == 302)
        confere("  evento inativo, inscricoes preservadas", _um(conectar, "SELECT ativo FROM evento WHERE id = %s", (eid,)) is False
                and _um(conectar, "SELECT count(*) FROM agendamento WHERE evento_id = %s", (eid,)) == 2)
        confere("  some da pagina publica", f"{PREFIXO} editado" not in html(cliente.get("/eventos")))
        confere("  continua no painel como Excluido", "Excluído" in html(cliente.get("/admin/eventos")))
        r = post(f"/admin/eventos/{eid}/reativar")
        confere("reativar -> volta a ativo", r.status_code == 302 and _um(conectar, "SELECT ativo FROM evento WHERE id = %s", (eid,)) is True)
        confere("excluir inexistente -> 404", post("/admin/eventos/999999/excluir").status_code == 404)

        print("== Inscritos e presenca manual (RF5, RF6)")
        r = cliente.get(f"/admin/eventos/{eid}/inscritos")
        corpo = html(r)
        confere("lista de inscritos mostra os dois", r.status_code == 200 and "Pessoa Um" in corpo and "Pessoa Dois" in corpo)
        confere("  mostra contagem de vagas", "2 de 2 vagas" in corpo)
        confere("inscritos de evento inexistente -> 404", cliente.get("/admin/eventos/999999/inscritos").status_code == 404)
        aid = _um(conectar, "SELECT id FROM agendamento WHERE email = 'um@exemplo.com' AND evento_id = %s", (eid,))
        r = post(f"/admin/inscritos/{aid}/presenca", {"presente": "1"}, com_csrf=False)
        confere("marcar sem CSRF -> 400", r.status_code == 400)
        r = post(f"/admin/inscritos/{aid}/presenca", {"presente": "1"})
        confere("marcar presenca -> 302 para a lista", r.status_code == 302 and f"/eventos/{eid}/inscritos" in r.headers["Location"])
        confere("  agendamento presente (manual) e visita criada", _sql(conectar, "SELECT presente, checkin_metodo FROM agendamento WHERE id = %s", (aid,), ler=True)[0] == (True, "manual")
                and _um(conectar, "SELECT count(*) FROM visita WHERE agendamento_id = %s", (aid,)) == 1)
        post(f"/admin/inscritos/{aid}/presenca", {"presente": "1"})
        confere("  marcar de novo nao duplica a visita", _um(conectar, "SELECT count(*) FROM visita WHERE agendamento_id = %s", (aid,)) == 1)
        confere("  lista mostra Presente", "Presente" in html(cliente.get(f"/admin/eventos/{eid}/inscritos")))
        post(f"/admin/inscritos/{aid}/presenca", {"presente": "0"})
        confere("desmarcar -> ausente e visita removida", _sql(conectar, "SELECT presente FROM agendamento WHERE id = %s", (aid,), ler=True)[0][0] is False
                and _um(conectar, "SELECT count(*) FROM visita WHERE agendamento_id = %s", (aid,)) == 0)
        confere("marcar inscricao inexistente -> 404", post("/admin/inscritos/999999/presenca", {"presente": "1"}).status_code == 404)

        print("== QR codes")
        r = cliente.get(f"/admin/eventos/{eid}/qr.png")
        confere("QR do evento -> imagem PNG" + ("" if qr_real else " (pacote qrcode falso neste teste)"),
                r.status_code == 200 and r.mimetype == "image/png" and r.data[:4] == b"\x89PNG", r.status_code)
        confere("  QR de evento inexistente -> 404", cliente.get("/admin/eventos/999999/qr.png").status_code == 404)
        r = cliente.get("/admin/qr-entrada.png")
        confere("QR da entrada -> imagem PNG", r.status_code == 200 and r.mimetype == "image/png")
        r = cliente.get("/admin/qr")
        confere("pagina do QR da entrada mostra o endereco", r.status_code == 200 and f"http://teste.local/presenca/{TOKEN_GERAL}" in html(r))
        antigo = _um(conectar, "SELECT token_checkin FROM evento WHERE id = %s", (eid,))
        r = post(f"/admin/eventos/{eid}/renovar-qr")
        novo = _um(conectar, "SELECT token_checkin FROM evento WHERE id = %s", (eid,))
        confere("renovar QR -> token novo", r.status_code == 302 and novo != antigo)
        confere("  o QR antigo deixa de valer", cliente.get(f"/checkin/{antigo}").status_code == 404)

        print("== Presenca por QR (RF8)")
        publico = app.test_client()
        r = publico.get(f"/presenca/{TOKEN_GERAL}")
        confere("QR da entrada abre o formulario (sem login)", r.status_code == 200 and 'name="cidade"' in html(r))
        r = publico.post(f"/presenca/{TOKEN_GERAL}", data={"nome": NOME_TESTE + "Visitante Geral", "cidade": "Cabo Frio", "estado": "RJ"})
        confere("envio valido -> 302", r.status_code == 302 and r.headers["Location"].endswith("/presenca-registrada"), r.status_code)
        confere("  gravou visita geral (sem evento) com cidade e UF", _sql(conectar, "SELECT evento_id, cidade, estado, metodo FROM visita WHERE nome = %s", (NOME_TESTE + "Visitante Geral",), ler=True)[0] == (None, "Cabo Frio", "RJ", "qrcode"))
        confere("  pagina de agradecimento", "Presença registrada" in html(publico.get("/presenca-registrada")))
        r = publico.post(f"/presenca/{TOKEN_GERAL}", data={"nome": NOME_TESTE + "<b>x</b>", "cidade": ""})
        confere("cidade vazia -> 400, mantem o digitado e escapa HTML", r.status_code == 400 and "cidade são obrigatórios" in html(r) and "<b>x</b>" not in html(r))
        r = publico.post(f"/presenca/{TOKEN_GERAL}", data={"nome": NOME_TESTE + "Robo", "cidade": "Rio", "campo_extra": "http://spam"})
        confere("campo-isca preenchido: finge sucesso e nao grava", r.status_code == 302 and _um(conectar, "SELECT count(*) FROM visita WHERE nome = %s", (NOME_TESTE + "Robo",)) == 0)
        confere("QR invalido -> 404 amigavel", publico.get("/presenca/token-que-nao-existe").status_code == 404
                and publico.post("/checkin/token-que-nao-existe", data={"nome": "A", "cidade": "B"}).status_code == 404)

        aberto, tok_aberto = _evento_sql(conectar, "janela aberta", 0, 3, janela_aberta=True)
        fechado, tok_fechado = _evento_sql(conectar, "janela fechada", 5, 3)
        con = conectar(); agendamento.agendar(con, aberto, "Fernanda Agendada", "fe@exemplo.com", "22988887777"); con.close()
        r = publico.get(f"/checkin/{tok_aberto}")
        confere("QR do evento dentro da janela -> formulario com o titulo", r.status_code == 200 and f"{PREFIXO} janela aberta" in html(r))
        confere("QR do evento fora da janela -> 403", publico.get(f"/checkin/{tok_fechado}").status_code == 403
                and publico.post(f"/checkin/{tok_fechado}", data={"nome": "A", "cidade": "B"}).status_code == 403)
        r = publico.post(f"/checkin/{tok_aberto}", data={"nome": NOME_TESTE + "Fernanda", "cidade": "Niterói", "estado": "RJ", "email": " FE@Exemplo.com "})
        confere("quem agendou: check-in -> 302", r.status_code == 302, r.status_code)
        confere("  agendamento marcado presente por qrcode e visita ligada", _sql(conectar, "SELECT presente, checkin_metodo FROM agendamento WHERE email = 'fe@exemplo.com' AND evento_id = %s", (aberto,), ler=True)[0] == (True, "qrcode")
                and _um(conectar, "SELECT count(*) FROM visita WHERE evento_id = %s AND agendamento_id IS NOT NULL", (aberto,)) == 1)
        r = publico.post(f"/checkin/{tok_aberto}", data={"nome": NOME_TESTE + "Fernanda", "cidade": "Niterói", "email": "fe@exemplo.com"})
        confere("mesma pessoa de novo -> 409 'ja registrou'", r.status_code == 409 and "já registrou" in html(r), r.status_code)
        r = publico.post(f"/checkin/{tok_aberto}", data={"nome": NOME_TESTE + "Avulso", "cidade": "Búzios", "estado": "RJ", "email": "avulso@exemplo.com"})
        confere("quem NAO agendou tambem registra presenca", r.status_code == 302 and _um(conectar, "SELECT count(*) FROM visita WHERE evento_id = %s AND agendamento_id IS NULL", (aberto,)) == 1)
        r = cliente.get(f"/admin/eventos/{aberto}/inscritos")
        confere("  admin ve a presenca avulsa na lista do evento", "Presenças sem agendamento" in html(r) and "Avulso" in html(r))

        print("== Limite de envios dos formularios publicos")
        livre, _t = _evento_sql(conectar, "limite envios", 4, 50)
        antigo_lim, portal.LIMITE_AGENDAR = portal.LIMITE_AGENDAR, (3, 600)
        auth._contagem.clear()
        try:
            codigos = [publico.post(f"/eventos/{livre}/agendar", data={"nome": "Pessoa", "email": f"lim{i}@exemplo.com", "telefone": "22999990000"}).status_code for i in range(4)]
            confere("agendar: 3 envios passam e o 4o e barrado (429)", codigos == [302, 302, 302, 429], codigos)
            confere("  o envio barrado nao gravou nada", _um(conectar, "SELECT count(*) FROM agendamento WHERE evento_id = %s", (livre,)) == 3)
            r = publico.post(f"/eventos/{livre}/agendar", data={"nome": "Robo", "email": "robo@exemplo.com", "telefone": "1", "campo_extra": "x"})
            confere("  mensagem amigavel", "Aguarde" in html(publico.post(f"/eventos/{livre}/agendar", data={"nome": "P", "email": "p@exemplo.com", "telefone": "1"})))
        finally:
            portal.LIMITE_AGENDAR = antigo_lim
            auth._contagem.clear()
        antigo_lim, portal.LIMITE_PRESENCA = portal.LIMITE_PRESENCA, (2, 600)
        try:
            codigos = [publico.post(f"/presenca/{TOKEN_GERAL}", data={"nome": NOME_TESTE + f"Lim{i}", "cidade": "Rio"}).status_code for i in range(3)]
            confere("presenca: 2 envios passam e o 3o e barrado (429)", codigos == [302, 302, 429], codigos)
        finally:
            portal.LIMITE_PRESENCA = antigo_lim
            auth._contagem.clear()

        print("== Dashboard (RF9)")
        r = cliente.get("/admin/dashboard")
        corpo = html(r)
        confere("dashboard abre", r.status_code == 200 and "visitas no total" in corpo)
        total = _um(conectar, "SELECT count(*) FROM visita")
        confere("  total confere com o banco", f'<span class="numero">{total}</span>' in corpo, total)
        confere("  mostra a cidade de origem", "Cabo Frio" in corpo and "Niterói" in corpo)
        confere("  somente dados agregados: sem nomes nem e-mails (RNF7)", "Fernanda" not in corpo and "fe@exemplo.com" not in corpo and "avulso@" not in corpo and "Visitante Geral" not in corpo)
        con = conectar()
        with con.cursor() as cur:
            import dashboard
            est = dashboard.estatisticas(cur)
        con.rollback(); con.close()
        confere("  grafico mensal tem 12 meses, sem pular nenhum", len(est["por_mes"]) == 12 and sum(m["visitas"] for m in est["por_mes"]) <= est["total"])
        confere("  mes atual tem as visitas de hoje", est["mes_atual"] >= 3, est["mes_atual"])
        confere("  taxa de comparecimento: 1 de 1 no evento com check-in",
                any(c["titulo"] == f"{PREFIXO} janela aberta" and c["agendados"] == 1 and c["presentes"] == 1 and c["taxa"] == 100 for c in est["comparecimento"]), est["comparecimento"])

        print("== Sessao")
        con = conectar()
        with con.cursor() as cur:
            auth.criar_admin(cur, "Outro Admin", "outro-admin-teste@exemplo.com", SENHA)
        con.commit(); con.close()
        outro = app.test_client()
        outro.get("/admin/login")
        post("/admin/login", {"email": "outro-admin-teste@exemplo.com", "senha": SENHA}, c=outro)
        confere("segundo administrador entra", outro.get("/admin/eventos").status_code == 200)
        _sql(conectar, "DELETE FROM administrador WHERE email = %s", ("outro-admin-teste@exemplo.com",))
        r = outro.get("/admin/eventos")
        confere("administrador removido perde o acesso na hora", r.status_code == 302 and "/admin/login" in r.headers["Location"], r.status_code)

        r = post("/admin/logout", com_csrf=False)
        confere("sair sem CSRF -> 400 (continua logado)", r.status_code == 400 and cliente.get("/admin/eventos").status_code == 200)
        r = post("/admin/logout")
        confere("sair -> 302 e perde o acesso", r.status_code == 302 and cliente.get("/admin/eventos").status_code == 302)

        print("== Erros")
        r = cliente.get("/admin/qualquer-coisa")
        confere("rota admin inexistente -> 404 amigavel (sem vazar nada)", r.status_code == 404 and "Tente" not in html(r) and "Traceback" not in html(r), r.status_code)
        orig = admin_eventos.listar_todos
        cliente.get("/admin/login")
        post("/admin/login", {"email": EMAIL, "senha": SENHA})
        admin_eventos.listar_todos = lambda _c: (_ for _ in ()).throw(RuntimeError("TESTE-ADMIN falha simulada"))
        try:
            r = cliente.get("/admin/eventos")
        finally:
            admin_eventos.listar_todos = orig
        corpo = html(r)
        confere("falha interna no painel -> 500 generico, sem detalhe tecnico", r.status_code == 500 and "Tente novamente" in corpo and "RuntimeError" not in corpo and "TESTE-ADMIN" not in corpo)
        confere("  gravada em log_erro (RNF4)", _um(conectar, "SELECT count(*) FROM log_erro WHERE mensagem LIKE %s", ("%TESTE-ADMIN%",)) == 1)
        r = publico.post(f"/presenca/{TOKEN_GERAL}", data={"nome": "x" * 100000, "cidade": "Rio"})
        confere("corpo de requisicao enorme -> recusado (413)", r.status_code == 413, r.status_code)
        confere("  413 com mensagem propria (nao 'pagina nao encontrada')", "Envio grande demais" in html(r))
        # --- entradas hostis (revisao)
        r = publico.post(f"/presenca/{TOKEN_GERAL}", data={"nome": "[TESTE-ADM] Ana", "cidade": "Rio"})
        confere("presenca com token geral valido segue funcionando", r.status_code in (200, 302), r.status_code)
        r = publico.get("/presenca/token-com-acento-çã")
        confere("token com acento na URL -> 404 amigavel, sem erro 500", r.status_code == 404, r.status_code)
        r = publico.post("/presenca/token-com-acento-çã", data={"nome": "[TESTE-ADM] Ana", "cidade": "Rio"})
        confere("  POST idem", r.status_code == 404, r.status_code)
        r = publico.post(f"/presenca/{TOKEN_GERAL}", data={"nome": "[TESTE-ADM] A\x00na", "cidade": "Rio"})
        confere("caractere nulo no nome -> dados invalidos (400), sem 500", r.status_code == 400, r.status_code)
        r = cliente.post("/admin/eventos/novo", data={"_csrf": "çãé", "titulo": "x"})
        confere("CSRF com acento -> recusado (nao 500)", r.status_code in (400, 403), r.status_code)
        cliente.get("/admin/login")
        r = publico.post("/admin/login", data={"email": EMAIL, "senha": SENHA, "_csrf": "ç"})
        confere("login com CSRF nao-ASCII -> recusado (nao 500)", r.status_code in (400, 403), r.status_code)
        r = publico.get("/presenca/" + "a" * 500)
        confere("token gigante -> 404", r.status_code == 404, r.status_code)
        con = conectar()
        try:
            with con.cursor() as cur:
                confere("telefone sem digitos -> DADOS_INVALIDOS", agendamento.agendar(con, 1, "Ana", "a@b.com", "abc")[0] == "DADOS_INVALIDOS")
                confere("e-mail sem @ -> DADOS_INVALIDOS", agendamento.agendar(con, 1, "Ana", "semarroba", "21999999999")[0] == "DADOS_INVALIDOS")
                confere("UF inexistente -> DADOS_INVALIDOS", checkin.registrar_visita(cur, TOKEN_GERAL, "[TESTE-ADM] Ana", "Rio", "ZZ", None) == "DADOS_INVALIDOS")
            con.rollback()
        finally:
            con.close()
    finally:
        _sql(conectar, "DELETE FROM administrador WHERE email = %s", ("outro-admin-teste@exemplo.com",))
        _limpar(conectar)
    print("\nfalhas:", falhas)
    return falhas


if __name__ == "__main__":
    sys.exit(1 if rodar(db.conectar) else 0)
