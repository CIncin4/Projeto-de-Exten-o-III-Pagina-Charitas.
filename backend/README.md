# Backend · Portal público do visitante (Sprint 2)

Telas públicas do SAP-Charitas feitas em Flask: **lista de eventos** (RF1), **agendamento com limite de vagas** (RF2 e RF7) e confirmação.

## Arquivos

| Arquivo | Função |
|---|---|
| `app.py` | Rotas do portal e tradução dos códigos de retorno em mensagens |
| `eventos.py` | Consultas da listagem (vagas calculadas no SQL; nunca expõe `token_checkin`) |
| `agendamento.py` | `agendar()`: inscrição com trava contra overbooking |
| `db.py` | Conexão com o banco (`DATABASE_URL` do `.env`) e gravação em `log_erro` |
| `checkin.py` | Presença por QR code (Sprint 3) |
| `templates/`, `static/` | Páginas HTML e CSS (mobile first, tema claro/escuro) |
| `testar_portal.py` | Teste das telas contra o banco |
| `testar_concorrencia.py` | Teste de concorrência do `agendar()` |

## Rotas

| Método | Rota | O que faz |
|---|---|---|
| GET | `/eventos` | Lista eventos ativos de hoje em diante, com vagas restantes |
| GET | `/eventos/<id>/agendar` | Formulário (404 se o evento não existe, está desativado ou já passou) |
| POST | `/eventos/<id>/agendar` | Chama `agendar()` e mostra o resultado |
| GET | `/eventos/<id>/confirmado` | Confirmação (após o POST, para o F5 não reenviar) |

| Código de `agendar()` | O que o visitante vê | HTTP |
|---|---|---|
| `OK` | Página "Agendamento confirmado" | 302 → 200 |
| `SEM_VAGAS` | "As vagas deste evento acabaram de esgotar…" | 409 |
| `JA_INSCRITO` | "Este e-mail já está inscrito neste evento." | 409 |
| `DADOS_INVALIDOS` | "Confira os campos…" (o que foi digitado volta preenchido) | 400 |
| `EVENTO_INATIVO` | "Evento não encontrado" | 404 |

Erros inesperados mostram uma mensagem genérica ao visitante (RNF5) e o detalhe técnico vai para a tabela `log_erro`.

## Como rodar no seu computador

```
cd backend
pip install -r requirements.txt     # com o .venv ativo
python app.py                       # abre em http://localhost:5000
```

O `.env` fica na raiz do projeto (veja `.env.example`) com `DATABASE_URL` do Session pooler do Supabase.
Para ver a página no celular na mesma rede Wi-Fi, use `flask --app app run --host 0.0.0.0` e abra `http://<IP do PC>:5000/eventos`.

## Testes

```
python testar_portal.py          # telas: lista, formulário, vagas, duplicado, erros
python testar_concorrencia.py    # 10 inscrições simultâneas em 5 vagas
```

Os dois criam eventos `[TESTE] ...` e apagam no final. Rode com os colegas fora do banco (limite de 15 conexões do Supabase).

## Observações

- Só aparecem eventos com data de hoje (fuso de São Paulo) em diante. Os eventos do `seed.sql` de 12 e 14/11 já passaram; para ver mais cards, crie eventos com datas futuras.
- A página não usa login nem cookies: o visitante só preenche o formulário.
- O campo escondido `website` é uma isca para robôs: se vier preenchido, o sistema finge sucesso e não grava nada.
