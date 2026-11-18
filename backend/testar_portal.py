"""
SAP-Charitas | Teste do portal publico (listagem + agendamento) contra o banco real.

Usa o cliente de teste do Flask (nao precisa subir o servidor). Cria eventos
'[TESTE] portal ...' e apaga tudo no final.

Rodar (com o .venv ativo e o .env configurado):   python testar_portal.py
"""
import secrets
import sys

import db

PREFIXO = "[TESTE] portal"
falhas = 0


def confere(nome, condicao, detalhe=""):
    global falhas
    falhas += 0 if condicao else 1
    print("OK    " if condicao else "FALHOU", nome, "" if condicao else f"-> {detalhe}")


def _criar_evento(conectar, sufixo, dias, limite, ativo=True):
    """dias: deslocamento em relacao a hoje (negativo = evento que ja passou)."""
    con = conectar()
    try:
        with con.cursor() as cur:
            cur.execute(
                """
                INSERT INTO evento (titulo, descricao, data_evento, horario, limite_vagas,
                                    token_checkin, checkin_abre_em, checkin_fecha_em, ativo)
                VALUES (%s, 'descricao de teste', (now() AT TIME ZONE 'America/Sao_Paulo')::date + %s,
                        '10:00', %s, %s, now(), now() + interval '2 hours', %s)
                RETURNING id, token_checkin
                """,
                (f"{PREFIXO} {sufixo}", dias, limite, secrets.token_urlsafe(16), ativo),
            )
            linha = cur.fetchone()
        con.commit()
        return linha
    finally:
        con.close()


def _contar(conectar, evento_id):
    con = conectar()
    try:
        with con.cursor() as cur:
            cur.execute("SELECT count(*) FROM agendamento WHERE evento_id = %s", (evento_id,))
            return cur.fetchone()[0]
    finally:
        con.close()


def _limpar(conectar):
    con = conectar()
    try:
        with con.cursor() as cur:
            cur.execute("DELETE FROM agendamento WHERE evento_id IN "
                        "(SELECT id FROM evento WHERE titulo LIKE %s)", (PREFIXO + "%",))
            cur.execute("DELETE FROM evento WHERE titulo LIKE %s", (PREFIXO + "%",))
            cur.execute("DELETE FROM log_erro WHERE mensagem LIKE %s", ("%TESTE-PORTAL%",))
        con.commit()
    finally:
        con.close()


def rodar(conectar):
    db.conectar = conectar          # o app usa db.conectar() em cada requisicao
    import app as portal            # importa depois do patch
    import eventos

    cliente = portal.app.test_client()
    _limpar(conectar)               # sobras de uma execucao interrompida
    try:
        livre, tok_livre = _criar_evento(conectar, "livre", 7, 5)
        lotado, _ = _criar_evento(conectar, "lotado", 8, 1)
        inativo, _ = _criar_evento(conectar, "inativo", 9, 5, ativo=False)
        passado, _ = _criar_evento(conectar, "passado", -3, 5)
        form = {"nome": "Maria Teste", "email": "maria.teste@exemplo.com", "telefone": "22999990000"}

        print("== Listagem")
        r = cliente.get("/eventos")
        html = r.get_data(as_text=True)
        confere("GET /eventos -> 200", r.status_code == 200, r.status_code)
        confere("mostra o evento com vagas", f"{PREFIXO} livre" in html and "5 vagas" in html)
        confere("nao mostra evento desativado", f"{PREFIXO} inativo" not in html)
        confere("nao mostra evento que ja passou", f"{PREFIXO} passado" not in html)
        confere("token do QR nunca aparece na pagina", tok_livre not in html)

        print("== Formulario")
        confere("GET agendar (evento ok) -> 200", cliente.get(f"/eventos/{livre}/agendar").status_code == 200)
        confere("evento desativado -> 404", cliente.get(f"/eventos/{inativo}/agendar").status_code == 404)
        confere("evento passado -> 404", cliente.get(f"/eventos/{passado}/agendar").status_code == 404)
        confere("evento inexistente -> 404", cliente.get("/eventos/999999/agendar").status_code == 404)

        print("== Agendamento")
        r = cliente.post(f"/eventos/{livre}/agendar", data=form)
        confere("POST valido -> redireciona", r.status_code == 302, r.status_code)
        r2 = cliente.get(r.headers["Location"])
        confere("pagina de confirmacao", r2.status_code == 200 and "Agendamento confirmado" in r2.get_data(as_text=True))
        confere("gravou 1 inscricao", _contar(conectar, livre) == 1, _contar(conectar, livre))
        confere("listagem mostra 4 vagas", "4 vagas" in cliente.get("/eventos").get_data(as_text=True))

        r = cliente.post(f"/eventos/{livre}/agendar", data={**form, "email": " MARIA.Teste@Exemplo.com "})
        confere("mesmo e-mail de novo -> 409 (maiusculas e espacos)", r.status_code == 409, r.status_code)
        confere("  mensagem amigavel", "já está inscrito" in r.get_data(as_text=True))
        confere("  nao duplicou", _contar(conectar, livre) == 1)

        cliente.post(f"/eventos/{lotado}/agendar", data=form)
        r = cliente.post(f"/eventos/{lotado}/agendar", data={**form, "email": "outra@exemplo.com"})
        confere("evento lotado -> 409", r.status_code == 409, r.status_code)
        confere("  mensagem de esgotado", "esgotar" in r.get_data(as_text=True))
        confere("  nao passou do limite", _contar(conectar, lotado) == 1)
        confere("listagem mostra Esgotado", "Esgotado" in cliente.get("/eventos").get_data(as_text=True))

        r = cliente.post(f"/eventos/{livre}/agendar", data={**form, "nome": "<b>x</b>", "email": ""})
        corpo = r.get_data(as_text=True)
        confere("campo vazio -> 400", r.status_code == 400, r.status_code)
        confere("  digitado volta no formulario, com HTML escapado", "&lt;b&gt;x&lt;/b&gt;" in corpo and "<b>x</b>" not in corpo)

        r = cliente.post(f"/eventos/{livre}/agendar", data={**form, "email": "robo@exemplo.com", "website": "http://spam"})
        confere("campo-isca preenchido: finge sucesso", r.status_code == 302)
        confere("  mas nao grava nada", _contar(conectar, livre) == 1)

        r = cliente.post(f"/eventos/{inativo}/agendar", data=form)
        confere("POST em evento desativado -> 404", r.status_code == 404, r.status_code)

        print("== Erros")
        confere("rota inexistente -> 404 amigavel", cliente.get("/qualquer-coisa").status_code == 404)
        original = eventos.listar_eventos
        eventos.listar_eventos = lambda _c: (_ for _ in ()).throw(RuntimeError("TESTE-PORTAL falha simulada"))
        try:
            r = cliente.get("/eventos")
        finally:
            eventos.listar_eventos = original
        corpo = r.get_data(as_text=True)
        confere("falha interna -> 500", r.status_code == 500, r.status_code)
        confere("  visitante ve mensagem generica, sem detalhe tecnico",
                "Tente novamente" in corpo and "RuntimeError" not in corpo and "TESTE-PORTAL" not in corpo)
        con = conectar()
        try:
            with con.cursor() as cur:
                cur.execute("SELECT count(*) FROM log_erro WHERE mensagem LIKE %s", ("%TESTE-PORTAL%",))
                confere("  erro gravado em log_erro", cur.fetchone()[0] == 1)
        finally:
            con.close()
    finally:
        _limpar(conectar)
    print("\nfalhas:", falhas)
    return falhas


if __name__ == "__main__":
    sys.exit(1 if rodar(db.conectar) else 0)
