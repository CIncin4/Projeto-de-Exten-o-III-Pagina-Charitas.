"""
SAP-Charitas | Conexao com o banco (PostgreSQL no Supabase).

A URL vem do arquivo .env (nunca do codigo): DATABASE_URL=postgresql://...
Use a string do "Session pooler" do Supabase (funciona em IPv4 no plano gratis).
"""
import os


def conectar():
    """Abre uma conexao nova. Quem chamou e responsavel por fechar."""
    import psycopg2
    from dotenv import load_dotenv

    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL nao encontrada. Crie o arquivo .env (veja .env.example).")
    return psycopg2.connect(url, connect_timeout=10)


def get_conexao():
    """Uma conexao por requisicao do Flask, fechada sozinha no fim (veja fechar_conexao)."""
    from flask import g
    if "con" not in g:
        g.con = conectar()
    return g.con


def fechar_conexao(_exc=None):
    from flask import g
    con = g.pop("con", None)
    if con is not None:
        try:
            con.close()
        except Exception:
            pass


def registrar_erro(origem: str, mensagem: str):
    """Grava em log_erro (RNF4). Nunca levanta excecao: o log nao pode derrubar a tela."""
    try:
        con = conectar()
        try:
            with con.cursor() as cur:
                cur.execute(
                    "INSERT INTO log_erro (origem, mensagem) VALUES (%s, %s)",
                    (origem[:100], mensagem),
                )
            con.commit()
        finally:
            con.close()
    except Exception:
        pass
