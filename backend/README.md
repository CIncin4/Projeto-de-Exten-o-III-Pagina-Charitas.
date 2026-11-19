# Backend · SAP-Charitas

Aplicação web em Flask (Python) com o **portal público do visitante** e o **painel da gestão**.

| Requisito | O que faz | Onde |
|---|---|---|
| RF1 | Lista de eventos com vagas restantes | `GET /eventos` |
| RF2, RF7 | Agendamento com bloqueio quando as vagas acabam | `/eventos/<id>/agendar`, `agendamento.py` |
| RF3 | Login do administrador (senha criptografada) | `/admin/login`, `auth.py` |
| RF4 | Criar, editar e excluir eventos (exclusão lógica) | `/admin/eventos` |
| RF5 | Lista de inscritos de cada evento | `/admin/eventos/<id>/inscritos` |
| RF6 | Marcar e desmarcar presença na lista | botão na lista de inscritos |
| RF8 | Formulário de presença por QR code (qualquer pessoa, com cidade) | `/presenca/<token>`, `/checkin/<token>` |
| RF9 | Dashboard de estatísticas das visitas | `/admin/dashboard` |
| RNF4, RNF5 | Erros viram mensagem genérica na tela e vão para `log_erro` | `app.py`, `db.py` |

## Arquivos

| Arquivo | Função |
|---|---|
| `app.py` | Portal público, formulário de presença, configuração e tratamento de erros |
| `admin.py` | Rotas do painel (`/admin/...`): login, eventos, inscritos, dashboard, QR |
| `auth.py` | Login, sessão, CSRF e limites de tentativas |
| `eventos.py` | Consultas da lista pública de eventos (nunca expõe o token do QR) |
| `admin_eventos.py` | Dados do painel: criar/editar/excluir evento, lista de inscritos |
| `agendamento.py` | `agendar()`: inscrição com trava contra overbooking |
| `checkin.py` | Lógica de presença: `registrar_visita`, `consultar_qr`, marcação manual, janela do check-in |
| `dashboard.py` | Estatísticas agregadas (sem nomes nem e-mails) |
| `qr.py` | Gera a imagem do QR code |
| `db.py` | Conexão com o banco e gravação em `log_erro` |
| `criar_admin.py` | Cria o primeiro administrador pelo terminal |
| `templates/`, `static/` | Páginas HTML e CSS (celular primeiro, tema claro/escuro) |
| `testar_portal.py`, `testar_admin.py`, `testar_concorrencia.py` | Testes contra o banco |

## Como rodar no seu computador

1. Crie o `.env` na **raiz do projeto**, copiando o `.env.example`, e preencha `DATABASE_URL` (Session pooler do Supabase), `TOKEN_PRESENCA_GERAL` e `SECRET_KEY`.
2. Com o `.venv` ativo:
```
cd backend
pip install -r requirements.txt
python criar_admin.py      # cria o SEU administrador (a senha não aparece na tela)
python app.py              # abre em http://localhost:5000
```
3. Entre em `http://localhost:5000/admin/login`.

Depois de criar o seu administrador, apague o de teste do `seed.sql` (`admin@exemplo.com`, senha `admin123`) no SQL Editor do Supabase. O comando está no cabeçalho do `criar_admin.py`.

**Testar no celular** (mesma rede Wi-Fi): rode `flask --app app run --host 0.0.0.0`, descubra o IP do PC (`ipconfig`) e abra `http://<IP>:5000/eventos`. Para o QR code apontar para esse endereço, coloque-o em `APP_BASE_URL` no `.env`.

## QR codes

- **Entrada do museu:** `/admin/qr` mostra o QR fixo (precisa de `TOKEN_PRESENCA_GERAL` no `.env`). Imprima e cole na entrada.
- **Cada evento:** o QR aparece na lista de inscritos. Só funciona de 30 minutos antes até 2 horas depois do horário do evento. Se vazar, use "Gerar novo QR" e o antigo para de funcionar.
- Quem escaneia preenche nome e cidade (estado e e-mail são opcionais), com ou sem agendamento. Se informar o e-mail do agendamento, a presença é marcada na lista do evento.

## Testes

```
python testar_portal.py          # telas públicas: lista, formulário, vagas, duplicados, erros
python testar_admin.py           # login, CRUD, inscritos, presença, QR, dashboard, segurança
python testar_concorrencia.py    # 10 inscrições simultâneas em 5 vagas
```

Todos criam dados `[TESTE] ...` e apagam no final. Rode com os colegas fora do banco (limite de 15 conexões do Supabase).

## Segurança, em resumo

- Senhas com bcrypt (pgcrypto, dentro do PostgreSQL); nunca em texto. Login com mensagem única para e-mail ou senha errados.
- Sessão por cookie assinado (`SECRET_KEY`), 8 horas, `HttpOnly` e `SameSite=Lax`. Todo POST do painel exige token CSRF.
- Bloqueio temporário após 5 logins errados (por e-mail e por IP) e limite de envios nos formulários públicos.
- Consultas sempre parametrizadas; HTML sempre escapado nos templates.
- O dashboard mostra só dados agregados (LGPD, RNF7).

## Limites conhecidos

- Os contadores de tentativas ficam na memória do servidor: reiniciar zera, e com vários processos (gunicorn com vários workers) cada um conta separado.
- O bloqueio de login por e-mail também significa que alguém pode, de propósito, travar o login de um administrador por 15 minutos. É o preço de não deixar adivinhar senha.
- A janela de check-in é sempre recalculada para o padrão (30 min antes e 2 h depois) quando o evento é editado.
- Com `TRUST_PROXY` desligado, atrás de um proxy todos os visitantes parecem ter o mesmo IP.
- Se a mesma pessoa se inscreve com um e-mail e registra presença pelo QR com outro, ela conta como duas pessoas no dashboard.
- A imagem do QR (`qrcode`) foi testada só com um substituto; confira a tela "QR codes" do painel na primeira vez.
- Validação de e-mail e telefone é básica de propósito (tem `@`; pelo menos 8 dígitos). Não confirma que existem.
