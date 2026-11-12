-- SAP-Charitas | Dados de exemplo (APENAS PARA TESTE, tudo ficticio)
-- Rode DEPOIS do schema.sql.

-- Necessario para gerar o hash da senha do admin de teste (bcrypt)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Admin de teste. Senha: admin123  (TROQUE antes de qualquer uso real)
INSERT INTO administrador (nome, email, senha_hash)
VALUES ('Admin Teste', 'admin@exemplo.com', crypt('admin123', gen_salt('bf')));

-- Eventos de exemplo (mesmos do mockup do PDF). Fuso: Brasilia (-03)
-- Janela de check-in: abre 30 min antes e fecha 2 h depois do inicio.
INSERT INTO evento (titulo, descricao, data_evento, horario, limite_vagas,
                    token_checkin, checkin_abre_em, checkin_fecha_em, criado_por)
VALUES
('Visita guiada - Casa de Acolhimento', 'Visita guiada pelo espaco do Charitas.',
 '2026-11-12', '09:00', 12,
 'token-teste-visita-guiada',
 TIMESTAMPTZ '2026-11-12 08:30:00-03', TIMESTAMPTZ '2026-11-12 11:00:00-03',
 (SELECT id FROM administrador WHERE email = 'admin@exemplo.com')),

('Oficina de artesanato solidario', 'Oficina aberta ao publico.',
 '2026-11-14', '14:00', 6,
 'token-teste-oficina-artesanato',
 TIMESTAMPTZ '2026-11-14 13:30:00-03', TIMESTAMPTZ '2026-11-14 16:00:00-03',
 (SELECT id FROM administrador WHERE email = 'admin@exemplo.com')),

('Feira beneficente do Charitas', 'Feira com barracas e apresentacoes.',
 '2026-11-21', '10:00', 20,
 'token-teste-feira-beneficente',
 TIMESTAMPTZ '2026-11-21 09:30:00-03', TIMESTAMPTZ '2026-11-21 12:00:00-03',
 (SELECT id FROM administrador WHERE email = 'admin@exemplo.com'));

-- Inscricoes de exemplo na visita guiada (2 ja marcadas como presentes)
INSERT INTO agendamento (evento_id, nome, email, telefone, presente, checkin_em, checkin_metodo)
SELECT e.id, v.nome, v.email, v.telefone, v.presente,
       CASE WHEN v.presente THEN now() END,
       CASE WHEN v.presente THEN v.metodo END
FROM evento e,
(VALUES
  ('Ana Beatriz Lima',      'ana.lima@exemplo.com',     '(21) 90000-0001', true,  'qrcode'),
  ('Carlos Eduardo Rocha',  'carlos.rocha@exemplo.com', '(21) 90000-0002', true,  'manual'),
  ('Fernanda Alves',        'fe.alves@exemplo.com',     '(21) 90000-0003', false, NULL),
  ('Joao Pedro Martins',    'jp.martins@exemplo.com',   '(21) 90000-0004', false, NULL),
  ('Luciana Prado',         'lu.prado@exemplo.com',     '(21) 90000-0005', false, NULL)
) AS v(nome, email, telefone, presente, metodo)
WHERE e.titulo = 'Visita guiada - Casa de Acolhimento';
