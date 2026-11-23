# SAP-Charitas

Sistema web de **agendamento de eventos** e **lista de presença digital** da **Casa de Cultura José de Dome (Charitas), Cabo Frio – RJ**.

Projeto de Extensão III, Universidade Veiga de Almeida (UVA).

O visitante vê os eventos, se inscreve pelo celular e registra presença lendo um QR code. A equipe da casa gerencia tudo por um painel protegido por login e acompanha os números em um dashboard.

---

## Como o site funciona

### Para o visitante (sem login)

| Tela | Endereço | O que faz |
|---|---|---|
| Lista de eventos | `/` | Mostra os próximos eventos, com data, horário e vagas restantes. |
| Inscrição | `/eventos/<id>/agendar` | Formulário com nome, e-mail e telefone. Garante a vaga e avisa quando o evento está lotado ou a pessoa já está inscrita. |
| Confirmação | `/eventos/<id>/confirmado` | Mostra que a inscrição foi feita. |
| Registro de presença | `/presenca/<código>` e `/checkin/<código>` | Aberto ao **escanear um QR code**. Pede nome, cidade, estado e e-mail (opcional). |

**Dois tipos de QR code**

- **QR da entrada do museu:** fixo, para quem chega sem ter agendado. Registra uma visita geral.
- **QR de cada evento:** só vale de **30 minutos antes** até **2 horas depois** do horário. Se a pessoa estava inscrita, a presença dela é marcada automaticamente.

### Para a equipe (área `/admin`, com login)

| Tela | Endereço | O que faz |
|---|---|---|
| Login | `/admin/login` | Entrada com e-mail e senha. |
| Início | `/admin/` | Atalhos (criar evento, ver inscritos, imprimir QR, ver números), números do mês e próximos eventos. |
| Eventos | `/admin/eventos` | Criar, editar, desativar e reativar eventos. |
| Inscritos | `/admin/eventos/<id>/inscritos` | Lista de inscritos e visitantes avulsos do evento, com botão para marcar ou desmarcar presença manualmente. |
| QR codes | `/admin/qr` | Imagens dos QR codes para baixar e imprimir. Permite renovar o QR de um evento. |
| Dashboard | `/admin/dashboard` | Visitas por mês, cidades de origem, comparecimento por evento e métodos de registro. |

O dashboard mostra **apenas dados agregados**, sem nomes nem e-mails (LGPD).

---

## Tecnologias

- **Python 3** com **Flask** (site e painel)
- **PostgreSQL** hospedado no **Supabase**, acessado com `psycopg2`
- **HTML/CSS** puros, sem frameworks de interface
- **qrcode** para gerar os QR codes
- Hospedagem sugerida: **Render**

---

## Como rodar no seu computador

Pré-requisitos: Python 3.10 ou superior e acesso ao banco do projeto no Supabase.

```powershell
# 1. Crie e ative o ambiente virtual (na raiz do projeto)
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Instale as dependências
cd backend
pip install -r requirements.txt
```

Em Linux ou macOS, ative com `source .venv/bin/activate`.

**3. Configure o `.env`** na raiz do projeto, copiando o `.env.example`:

| Variável | Para que serve |
|---|---|
| `DATABASE_URL` | Endereço do banco no Supabase (use o **Session pooler**). |
| `SECRET_KEY` | Chave que assina a sessão de login. Gere com `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `TOKEN_PRESENCA_GERAL` | Código do QR fixo da entrada. Gere com `python -c "import secrets; print(secrets.token_urlsafe(16))"`. |
| `APP_BASE_URL` | Endereço do site, sem barra no final (ex.: `http://localhost:5000`). É o endereço que vai dentro dos QR codes. |
| `COOKIE_SECURE` | Use `1` quando o site tiver HTTPS. |
| `TRUST_PROXY` | Use `1` quando o site ficar atrás de um proxy (Render, por exemplo). |

> O arquivo `.env` **nunca** deve ir para o GitHub. Ele já está no `.gitignore`.

**4. Crie o primeiro administrador:**

```powershell
python criar_admin.py
```

**5. Suba o servidor:**

```powershell
python app.py
```

Abra `http://localhost:5000` (site) e `http://localhost:5000/admin/login` (painel).

---

## Testes

Rodam contra o banco configurado no `.env`, criam dados de teste e apagam tudo no final. Rode com os colegas fora do banco, por causa do limite de 15 conexões do Supabase.

```powershell
cd backend
python testar_portal.py          # telas públicas e inscrição
python testar_admin.py           # login, eventos, presença, QR, dashboard e segurança
python testar_concorrencia.py    # 10 inscrições simultâneas disputando 5 vagas
```

---

## Publicar online (Render)

1. Envie o código para a branch `main` do GitHub.
2. No Render, crie um **Blueprint** apontando para este repositório. Ele lê o `render.yaml`.
3. Preencha `DATABASE_URL`, `SECRET_KEY`, `TOKEN_PRESENCA_GERAL` e `APP_BASE_URL` no painel do Render, com valores novos (não reaproveite os de teste).
4. Depois do deploy, entre em `/admin/login`, abra `/admin/qr` e só então imprima os QR codes.

Cada push na `main` atualiza o site automaticamente.

---

## Segurança

- Senhas guardadas com **bcrypt** (calculado dentro do PostgreSQL), nunca em texto.
- Sessão por cookie assinado, válida por 8 horas. Todo envio de formulário do painel exige token **CSRF**.
- Bloqueio temporário depois de 5 tentativas de login erradas.
- Limite de envios nos formulários públicos e campo oculto contra robôs.
- Todas as consultas ao banco são parametrizadas, e o HTML é sempre escapado.
- Eventos nunca são apagados de verdade: a exclusão é lógica e preserva o histórico de inscrições.

## Limitações conhecidas

- Os contadores de tentativas ficam na memória do servidor: reiniciar zera, e por isso o deploy usa um único processo.
- O bloqueio de login por e-mail permite que alguém trave, de propósito, o login de um administrador por 15 minutos.
- Se a mesma pessoa se inscreve com um e-mail e registra presença pelo QR com outro, conta como duas pessoas no dashboard.
- Não há recuperação de senha: a troca é feita direto no banco.
- No plano gratuito do Render, o primeiro acesso depois de um tempo parado leva cerca de 1 minuto.

---

## Equipe

Projeto desenvolvido por estudantes da UVA para a Casa de Cultura José de Dome (Charitas), Cabo Frio.
