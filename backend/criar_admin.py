"""
SAP-Charitas | Cria o primeiro administrador (ou mais um) direto no banco.

Uso (com o .venv ativo, dentro de backend/):
    python criar_admin.py

Pergunta nome, e-mail e senha (a senha nao aparece na tela) e grava com bcrypt.
Depois de criar o seu administrador, apague o de teste do seed.sql no SQL Editor do Supabase:
    DELETE FROM administrador WHERE email = 'admin@exemplo.com';
(se ele tiver criado eventos, rode antes: UPDATE evento SET criado_por = NULL WHERE criado_por = 1;
 confira o id dele com SELECT id, email FROM administrador;)
"""
import getpass
import sys

import auth
import db


def main():
    nome = input("Nome: ").strip()
    email = input("E-mail: ").strip()
    senha = getpass.getpass(f"Senha ({auth.MIN_SENHA} a {auth.MAX_SENHA} caracteres): ")
    if senha != getpass.getpass("Repita a senha: "):
        print("As senhas nao conferem.")
        return 1
    con = db.conectar()
    try:
        with con.cursor() as cur:
            codigo = auth.criar_admin(cur, nome, email, senha)
        if codigo == "OK":
            con.commit()
            print("Administrador criado. Entre em /admin/login.")
            return 0
        con.rollback()
        print({"EMAIL_EXISTE": "Ja existe um administrador com esse e-mail.",
               "DADOS_INVALIDOS": "Dados invalidos: confira nome, e-mail e o tamanho da senha."}[codigo])
        return 1
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())
