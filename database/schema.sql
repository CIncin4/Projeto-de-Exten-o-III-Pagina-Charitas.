-- SAP-Charitas | Esquema PostgreSQL (Sprint 1)
-- Inclui check-in por QR code (token por evento + janela de tempo)
-- e check-in manual do administrador como plano B.

CREATE TABLE administrador (
    id          INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome        VARCHAR(100) NOT NULL,
    email       VARCHAR(150) NOT NULL UNIQUE,
    senha_hash  VARCHAR(255) NOT NULL,           -- RNF2: nunca guardar senha em texto
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE evento (
    id               INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    titulo           VARCHAR(150) NOT NULL,
    descricao        TEXT,
    data_evento      DATE NOT NULL,
    horario          TIME NOT NULL,
    limite_vagas     INT  NOT NULL CHECK (limite_vagas > 0),

    -- Check-in por QR code
    token_checkin    VARCHAR(64) NOT NULL UNIQUE,  -- gerado pelo backend (secrets.token_urlsafe)
    checkin_abre_em  TIMESTAMPTZ NOT NULL,         -- inicio da janela
    checkin_fecha_em TIMESTAMPTZ NOT NULL,         -- fim da janela

    ativo            BOOLEAN NOT NULL DEFAULT true, -- exclusao logica (preserva historico)
    criado_por       INT REFERENCES administrador(id),
    criado_em        TIMESTAMPTZ NOT NULL DEFAULT now(),

    CHECK (checkin_fecha_em > checkin_abre_em)
);

CREATE TABLE agendamento (
    id              INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    evento_id       INT NOT NULL REFERENCES evento(id),
    nome            VARCHAR(100) NOT NULL,
    email           VARCHAR(150) NOT NULL,         -- o backend salva sempre em minusculas
    telefone        VARCHAR(20)  NOT NULL,
    presente        BOOLEAN NOT NULL DEFAULT false,
    checkin_em      TIMESTAMPTZ,
    checkin_metodo  VARCHAR(10) CHECK (checkin_metodo IN ('qrcode', 'manual')),
    agendado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (evento_id, email),                     -- impede inscricao duplicada
    CHECK (presente = false OR checkin_em IS NOT NULL)
);

CREATE INDEX idx_agendamento_evento ON agendamento(evento_id);

CREATE TABLE log_erro (
    id         INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    data_hora  TIMESTAMPTZ NOT NULL DEFAULT now(),
    origem     VARCHAR(100),
    mensagem   TEXT NOT NULL
);
