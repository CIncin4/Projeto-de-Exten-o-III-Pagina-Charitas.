"""
SAP-Charitas | Teste de concorrencia do agendamento (RF7).

Dispara varias inscricoes ao mesmo tempo e confere que o limite de vagas nunca estoura.
Cria um evento "[TESTE]" e apaga tudo no fim. Use um banco de TESTE ou, no Supabase,
rode quando ninguem estiver usando o sistema.

    pip install psycopg2-binary python-dotenv
    python testar_concorrencia.py

Usa 10 conexoes simultaneas (o Supabase gratuito aceita ate 15 no Session pooler).
Para mudar: defina TESTE_TENTATIVAS (precisa ser maior que 5, o limite de vagas do teste).
"""
import os
import secrets
import sys
import threading
import time
from collections import Counter

from agendamento import agendar


def _criar_evento(conectar, limite, ativo=True):
    con = conectar()
    with con.cursor() as cur:
        cur.execute(
            """
            INSERT INTO evento (titulo, data_evento, horario, limite_vagas, ativo,
                                token_checkin, checkin_abre_em, checkin_fecha_em)
            VALUES ('[TESTE] concorrencia', current_date + 30, '10:00', %s, %s,
                    %s, now(), now() + interval '2 hours')
            RETURNING id
            """,
            (limite, ativo, secrets.token_urlsafe(16)),
        )
        (evento_id,) = cur.fetchone()
    con.commit()
    con.close()
    return evento_id


def _disparar(conectar, evento_id, emails):
    """Abre TODAS as conexoes antes e so entao dispara as inscricoes juntas.
    Assim, se o banco recusar alguma conexao, o teste para com uma mensagem clara
    em vez de ficar esperando as outras threads."""
    conexoes = []
    try:
        for _ in emails:
            conexoes.append(conectar())
    except Exception:
        for c in conexoes:
            c.close()
        print(f"\nNao foi possivel abrir {len(emails)} conexoes ao mesmo tempo "
              f"(abriu {len(conexoes)}). O plano gratuito do Supabase aceita ate 15 no Session pooler:"
              " diminua TESTE_TENTATIVAS ou feche outros programas conectados ao banco.")
        raise

    resultados, erros = [], []
    largada = threading.Barrier(len(emails))

    def tarefa(con, email):
        try:
            largada.wait()
            resultados.append(agendar(con, evento_id, "Pessoa Teste", email, "(21) 90000-0000")[0])
        except Exception as e:  # noqa: BLE001
            erros.append(e)
        finally:
            con.close()

    threads = [threading.Thread(target=tarefa, args=(c, e)) for c, e in zip(conexoes, emails)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    if erros:
        raise erros[0]
    return Counter(resultados)


def _contar(conectar, evento_id):
    con = conectar()
    with con.cursor() as cur:
        cur.execute("SELECT count(*) FROM agendamento WHERE evento_id = %s", (evento_id,))
        (n,) = cur.fetchone()
    con.close()
    return n


def rodar(conectar, limite=5, tentativas=10):
    falhas, eventos = 0, []

    def confere(nome, obtido, esperado):
        nonlocal falhas
        ok = obtido == esperado
        falhas += 0 if ok else 1
        print(("OK     " if ok else "FALHOU ") + nome, "->", obtido, "" if ok else f"(esperado {esperado})")

    try:
        # 1) muita gente, emails diferentes, poucas vagas
        ev = _criar_evento(conectar, limite); eventos.append(ev)
        r = _disparar(conectar, ev, [f"teste{i}@exemplo.com" for i in range(tentativas)])
        confere(f"{tentativas} inscricoes simultaneas, {limite} vagas: aceitas", r["OK"], limite)
        confere("  recusadas por falta de vagas", r["SEM_VAGAS"], tentativas - limite)
        confere("  linhas gravadas no banco", _contar(conectar, ev), limite)

        # 2) a mesma pessoa clicando varias vezes ao mesmo tempo
        ev = _criar_evento(conectar, limite); eventos.append(ev)
        r = _disparar(conectar, ev, ["mesma@exemplo.com"] * 8)
        confere("8 cliques simultaneos da mesma pessoa: aceito", r["OK"], 1)
        confere("  os outros viram JA_INSCRITO", r["JA_INSCRITO"], 7)
        confere("  linhas gravadas no banco", _contar(conectar, ev), 1)

        # 3) casos simples
        con = conectar()
        confere("e-mail com maiusculas e espacos", agendar(con, ev, "Ana", "  MESMA@Exemplo.com ", "1")[0], "JA_INSCRITO")
        confere("campo vazio", agendar(con, ev, "Ana", "", "1")[0], "DADOS_INVALIDOS")
        confere("evento que nao existe", agendar(con, -1, "Ana", "a@exemplo.com", "1")[0], "EVENTO_INATIVO")
        con.close()
        ev = _criar_evento(conectar, limite, ativo=False); eventos.append(ev)
        con = conectar()
        confere("evento desativado", agendar(con, ev, "Ana", "a@exemplo.com", "1")[0], "EVENTO_INATIVO")
        con.close()
    finally:
        if eventos:  # limpa os eventos [TESTE] criados, mesmo se o teste falhar no meio
            _limpar(conectar, eventos)
    print("\nfalhas:", falhas)
    return falhas == 0


def _limpar(conectar, eventos, tentativas=5):
    """Apaga os eventos de teste. Tenta de novo se o banco recusar a conexao
    (logo apos um estouro de conexoes o servidor ainda esta liberando as vagas)."""
    for n in range(1, tentativas + 1):
        try:
            con = conectar()
            with con.cursor() as cur:
                for ev in eventos:
                    if _tem_visita(cur):
                        cur.execute("DELETE FROM visita WHERE evento_id = %s", (ev,))
                    cur.execute("DELETE FROM agendamento WHERE evento_id = %s", (ev,))
                    cur.execute("DELETE FROM evento WHERE id = %s", (ev,))
            con.commit()
            con.close()
            return
        except Exception:  # noqa: BLE001
            time.sleep(1)
    print("\nATENCAO: nao consegui apagar os eventos de teste. Apague pelo SQL Editor do Supabase:\n"
          "  DELETE FROM agendamento WHERE evento_id IN (SELECT id FROM evento WHERE titulo LIKE '[TESTE]%');\n"
          "  DELETE FROM evento WHERE titulo LIKE '[TESTE]%';")


def _tem_visita(cur):
    cur.execute("SELECT to_regclass('public.visita') IS NOT NULL")
    return cur.fetchone()[0]


if __name__ == "__main__":
    import psycopg2
    from dotenv import load_dotenv

    load_dotenv()
    url = os.environ["DATABASE_URL"]
    # Supabase gratuito: Session pooler aceita ate 15 conexoes; 10 deixa folga.
    tentativas = int(os.environ.get("TESTE_TENTATIVAS", 10))
    sys.exit(0 if rodar(lambda: psycopg2.connect(url), tentativas=tentativas) else 1)
