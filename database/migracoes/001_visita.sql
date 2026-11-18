-- SAP-Charitas | Migracao 001: registro de visitas (formulario de presenca + dashboard)
-- Rode UMA vez, no SQL Editor do Supabase, depois do schema.sql e do seed.sql.
-- Nao edite o schema.sql original: mudancas novas entram como migracao.
--
-- Cada linha de "visita" e uma presenca registrada:
--   * pelo formulario publico (QR code), por qualquer pessoa, com ou sem agendamento;
--   * ou pelo administrador, marcando a presenca na lista do evento (RF6).
-- O dashboard conta as linhas desta tabela.

CREATE TABLE visita (
    id              INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    evento_id       INT REFERENCES evento(id),                      -- NULL = visita geral ao museu
    agendamento_id  INT REFERENCES agendamento(id) ON DELETE SET NULL,  -- preenchido se a pessoa tinha agendado
    nome            VARCHAR(100) NOT NULL,
    email           VARCHAR(150),                                   -- opcional; em minusculas
    cidade          VARCHAR(100),                                   -- obrigatoria no formulario; nula se o admin marcou a presenca a mao
    estado          VARCHAR(2),                                     -- UF (ex.: RJ); opcional, para visitantes de fora do Brasil
    metodo          VARCHAR(10) NOT NULL CHECK (metodo IN ('qrcode', 'manual')),
    registrada_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A mesma pessoa (e-mail) nao registra presenca duas vezes no mesmo evento.
-- Visitas gerais (sem evento) podem se repetir, pois a pessoa pode voltar outro dia.
CREATE UNIQUE INDEX uq_visita_evento_email
    ON visita (evento_id, email)
    WHERE evento_id IS NOT NULL AND email IS NOT NULL;

CREATE INDEX idx_visita_registrada_em ON visita (registrada_em);
CREATE INDEX idx_visita_evento        ON visita (evento_id);

-- Mesma protecao das outras tabelas: a API publica do Supabase nao enxerga os dados.
ALTER TABLE visita ENABLE ROW LEVEL SECURITY;

-- Aproveita as presencas que ja existem em "agendamento" (dados de teste do seed.sql).
INSERT INTO visita (evento_id, agendamento_id, nome, email, metodo, registrada_em)
SELECT a.evento_id, a.id, a.nome, a.email, COALESCE(a.checkin_metodo, 'manual'), a.checkin_em
FROM agendamento a
WHERE a.presente = true
  AND NOT EXISTS (SELECT 1 FROM visita v WHERE v.agendamento_id = a.id);
