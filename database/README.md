# Banco de dados | SAP-Charitas

Banco **PostgreSQL** (Supabase) do sistema de agendamento e presenca do Charitas.

## Arquivos

| Arquivo | Para que serve |
|---|---|
| `schema.sql` | Cria as tabelas da Sprint 1 (`administrador`, `evento`, `agendamento`, `log_erro`) |
| `seed.sql` | Dados ficticios para teste (1 admin, 3 eventos, 5 inscricoes) |
| `migracoes/001_visita.sql` | Cria a tabela `visita` (formulario de presenca + dashboard) |
| `migracoes/002_seed_visitas.sql` | 14 visitas ficticias (ago-nov/2026) para testar o dashboard |
| `consultas_dashboard.sql` | Consultas prontas das estatisticas do administrador (RF9) |
| `modelagem/` | Diagramas (MER conceitual e logico) e arquivo-fonte do brModelo |

## Tabelas em resumo

- **administrador**: login da gestao. A senha e guardada como hash (RNF2).
- **evento**: titulo, data, horario, limite de vagas, token do QR e janela de check-in.
- **agendamento**: inscricao de um visitante em um evento, com `presente`, `checkin_em` e `checkin_metodo`.
- **visita**: cada presenca registrada, com ou sem agendamento (RF8). Guarda nome, e-mail (opcional),
  **cidade e UF** de origem, evento (vazio = visita geral ao museu) e o metodo (`qrcode` ou `manual`).
  E a tabela que o dashboard conta (RF9).
- **log_erro**: falhas do sistema (RNF4).

Regras importantes:
- Uma pessoa (mesmo e-mail) nao se inscreve duas vezes no mesmo evento, nem registra presenca duas vezes nele.
- O limite de vagas e verificado no backend, dentro de uma transacao (RF7).
- E-mails sao salvos em **minusculas**.
- Todas as tabelas tem RLS ativo; o backend se conecta direto pelo `DATABASE_URL`.
- O dashboard mostra so numeros agregados (LGPD). As consultas agrupam no horario de Brasilia.

## Como rodar

### Supabase (SQL Editor, uma query por arquivo, nesta ordem)

1. `schema.sql`
2. `seed.sql` (opcional, dados de teste)
3. `migracoes/001_visita.sql`
4. `migracoes/002_seed_visitas.sql` (opcional, para testar o dashboard)

Cada arquivo deve rodar **uma unica vez**: rodar de novo da erro de "already exists" ou duplica dados de teste.

### PostgreSQL local

```bash
createdb charitas
psql -d charitas -f schema.sql
psql -d charitas -f seed.sql
psql -d charitas -f migracoes/001_visita.sql
psql -d charitas -f migracoes/002_seed_visitas.sql
```

## Conexao

Copie `.env.example` (na raiz do projeto) para `.env` e preencha `DATABASE_URL` e `TOKEN_PRESENCA_GERAL`.
**Nunca** suba o `.env` para o GitHub.

## Alteracoes no esquema

Nao edite o `schema.sql` original: crie um novo script em `migracoes/` (ex.: `003_descricao.sql`) e avise o grupo.
