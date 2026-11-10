# Banco de dados | SAP-Charitas

Banco **PostgreSQL** do sistema de agendamento e lista de presenca do Charitas.

## Arquivos

| Arquivo | Para que serve |
|---|---|
| `schema.sql` | Cria as tabelas (`administrador`, `evento`, `agendamento`, `log_erro`) |
| `seed.sql` | Dados ficticios para teste (1 admin, 3 eventos, 5 inscricoes) |
| `modelagem/` | Diagramas (MER conceitual e logico) e arquivo-fonte do brModelo |

## Tabelas em resumo

- **administrador**: login da gestao. A senha e guardada como hash (RNF2).
- **evento**: titulo, data, horario, limite de vagas, token do QR code e janela de check-in.
- **agendamento**: inscricao de um visitante em um evento, com `presente`, `checkin_em` e `checkin_metodo` (`qrcode` ou `manual`).
- **log_erro**: falhas do sistema (RNF4).

Regras importantes:
- Uma pessoa (mesmo e-mail) nao se inscreve duas vezes no mesmo evento.
- O limite de vagas e verificado no backend, dentro de uma transacao (RF7).
- E-mails sao salvos em **minusculas**.

## Como rodar

### Supabase

1. Abra o projeto, va em **SQL Editor** e clique em **New query**.
2. Cole o conteudo de `schema.sql` e clique em **Run**.
3. (Opcional) Faca o mesmo com `seed.sql` para ter dados de teste.
4. Ative a seguranca por linha para a API publica nao expor as tabelas:

```sql
ALTER TABLE administrador ENABLE ROW LEVEL SECURITY;
ALTER TABLE evento        ENABLE ROW LEVEL SECURITY;
ALTER TABLE agendamento   ENABLE ROW LEVEL SECURITY;
ALTER TABLE log_erro      ENABLE ROW LEVEL SECURITY;
```

O backend Python se conecta direto pelo `DATABASE_URL`, entao nao e afetado.

### PostgreSQL local

```bash
createdb charitas
psql -d charitas -f schema.sql
psql -d charitas -f seed.sql
```

## Conexao

Copie `.env.example` (na raiz do projeto) para `.env` e preencha `DATABASE_URL`.
**Nunca** suba o `.env` para o GitHub.

## Alteracoes no esquema

Depois que o banco estiver na nuvem com dados, nao edite o `schema.sql` original:
crie um novo script de migracao (ex.: `migracoes/001_descricao.sql`) e avise o grupo.
