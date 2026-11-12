#importa e conectar com os database

import psycopg2
import os
import secrets 

from dotenv import load_dotenv
from datetime import datetime,timedelta 

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

conexao = psycopg2.connect(DATABASE_URL)

cursor = conexao.cursor()



def cadastrar_evento(): 
    titulo = input("Titulo do evento:")
    descricao = input("Descrição:")
    data_evento = input ("Data (DD-MM-AAAA):")
    horario = input ("Horario(HH:MM)")
    limite_vagas = int(input("Limite de vagas:"))

    token = secrets.token_urlsafe(32)

    checkin_abre = datetime.strptime(
        data_evento + " 13:00",
        "%d-%m-%Y %H:%M"
    )
    checkin_fecha = checkin_abre + timedelta(hours=5)


#Parte do CRUD 

#CREATE

comando = """
   INSERT INTO evento (
   titulo,
   descricao,
   data_evento,
   horario,
   limite_vagas,
   token_checkin,
   checkin_abre_em,
   checkin_fecha_em
 )
VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
"""
valores = (
 "titulo",
 "descriçao",
 "data_evento",
 "horario",
 "limite_vagas",
 "token_checkin"
 "checkin_abre_em",
 "checkin_fecha_em"
)
cursor.execute(comando,valores)
conexao.commit()

print ("Evento Cadastrado!")

#READ

def listar_eventos():
    comando="""
SELECT id,titulo,descricao,data_evento,horario,limite_vagas,ativo

FROM evento
WHERE ativo = TRUE
ORDER BY data_evento
"""

cursor.execute(comando) 
eventos = cursor.fetchall()

for evento in eventos:
    print("ID:",evento[0])
    print("Título:",evento [1])
    print("Descrição:",evento[2])
    print("Data:",evento[3])
    print("Horário:",evento[4])
    print("Vagas:",evento[5])
    print("Ativo:",evento[6])


#menu teste do crud, provalvemente irei deletar depois

while True:
    print("\n MENU TESTE") 
    print("1 - Cadastra evento")
    print("2 - Listar eventos")
    print("0 - Sair")

    opcao = input("Escolher Opção: ")

    try:
        if opcao == "1":
            cadastrar_evento()
        elif opcao == "2":
            listar_eventos()
        elif opcao == "0":
            print("Encerramento do sistema...")
            break
        else:
            print("Opção inválida")

    except (psycopg2.Error, ValueError) as erro:
        conexao.rollback()
        print("Erro:", erro)

<<<<<<< HEAD
#parte do update aqui!#  

def atualizar_evento():
    listar_eventos()

    id_evento = int(input("\nDigite o ID do evento que deseja atualizar: "))

    comando = """
        SELECT id, titulo, descricao, data_evento, horario, limite_vagas
        FROM evento
        WHERE id = %s AND ativo = TRUE
    """

    cursor.execute(comando, (id_evento,))
    evento = cursor.fetchone()

    if evento is None:
        print("Evento não encontrado!")
        return

    print("\n--- DADOS ATUAIS ---")
    print("Título:", evento[1])
    print("Descrição:", evento[2])
    print("Data:", evento[3])
    print("Horário:", evento[4])
    print("Limite de vagas:", evento[5])

    print("\n--- NOVOS DADOS ---")

    titulo = input("Novo título: ")
    descricao = input("Nova descrição: ")
    data_evento = input("Nova data (DD-MM-AAAA): ")
    horario = input("Novo horário (HH:MM): ")
    limite_vagas = int(input("Novo limite de vagas: "))

    # Essa parte e para testar a conversao da data, provavelmente irei deletar depois e mudar
    data_convertida = datetime.strptime(
        data_evento, "%d-%m-%Y"
    ).date()

    datetime.strptime(horario, "%H:%M")

    if limite_vagas <= 0:
        print("O limite de vagas deve ser maior que zero!")
        return

    checkin_abre = datetime.strptime(
        data_evento + " 13:00",
        "%d-%m-%Y %H:%M"
    )

    checkin_fecha = checkin_abre + timedelta(hours=5)

    #------------
    
    comando = """
        UPDATE evento
        SET titulo = %s,
            descricao = %s,
            data_evento = %s,
            horario = %s,
            limite_vagas = %s,
            checkin_abre_em = %s,
            checkin_fecha_em = %s
        WHERE id = %s AND ativo = TRUE
    """

    valores = (
        titulo,
        descricao,
        data_convertida,
        horario,
        limite_vagas,
        checkin_abre,
        checkin_fecha,
        id_evento
    )

    cursor.execute(comando, valores)
    conexao.commit()

    print("\nEvento atualizado com sucesso!")
=======
#parte do update aqui! 
>>>>>>> 4d06559629e05fcb2fba5105663bee15eca99e28


#parte do delete aqui!


#fecha conexao
cursor.close()
conexao.close()
