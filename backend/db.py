"""
SAP-Charitas | Conexao com o banco (PostgreSQL no Supabase).

A URL vem do arquivo .env (nunca do codigo): DATABASE_URL=postgresql://...
Use a string do "Session pooler" do Supabase (funciona em IPv4 no plano gratis).
"""
import os


def conectar():
    """Abre uma conexao nova. Quem chamou e responsavel por fechar (o app.py ja faz isso)."""
    import psycopg2
    from dotenv import load_dotenv

    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL nao encontrada. Crie o arquivo .env (veja .env.example).")
    return psycopg2.connect(url, connect_timeout=10)


def registrar_erro(origem: str, mensagem: str):
    """Grava em log_erro (tabela do schema). Nunca levanta excecao: log nao pode derrubar a tela."""
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
