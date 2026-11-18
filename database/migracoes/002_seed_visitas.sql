-- SAP-Charitas | Visitas de exemplo para testar o dashboard (APENAS TESTE, tudo ficticio)
-- Rode depois da migracao 001. Visitas gerais (sem evento), de agosto a novembro de 2026.
-- Para limpar depois: DELETE FROM visita WHERE nome LIKE '[TESTE]%';

INSERT INTO visita (evento_id, nome, cidade, estado, metodo, registrada_em) VALUES
  (NULL, '[TESTE] Visitante 01', 'Cabo Frio',            'RJ', 'qrcode', TIMESTAMPTZ '2026-08-08 10:15:00-03'),
  (NULL, '[TESTE] Visitante 02', 'Arraial do Cabo',      'RJ', 'qrcode', TIMESTAMPTZ '2026-08-15 14:40:00-03'),
  (NULL, '[TESTE] Visitante 03', 'Rio de Janeiro',       'RJ', 'qrcode', TIMESTAMPTZ '2026-08-22 11:05:00-03'),
  (NULL, '[TESTE] Visitante 04', 'Cabo Frio',            'RJ', 'qrcode', TIMESTAMPTZ '2026-09-05 09:50:00-03'),
  (NULL, '[TESTE] Visitante 05', 'Búzios',               'RJ', 'qrcode', TIMESTAMPTZ '2026-09-12 15:20:00-03'),
  (NULL, '[TESTE] Visitante 06', 'São Paulo',            'SP', 'qrcode', TIMESTAMPTZ '2026-09-19 16:10:00-03'),
  (NULL, '[TESTE] Visitante 07', 'Cabo Frio',            'RJ', 'qrcode', TIMESTAMPTZ '2026-10-03 10:30:00-03'),
  (NULL, '[TESTE] Visitante 08', 'São Pedro da Aldeia',  'RJ', 'qrcode', TIMESTAMPTZ '2026-10-10 11:45:00-03'),
  (NULL, '[TESTE] Visitante 09', 'Niterói',              'RJ', 'qrcode', TIMESTAMPTZ '2026-10-10 14:20:00-03'),
  (NULL, '[TESTE] Visitante 10', 'Belo Horizonte',       'MG', 'qrcode', TIMESTAMPTZ '2026-10-17 10:05:00-03'),
  (NULL, '[TESTE] Visitante 11', 'Cabo Frio',            'RJ', 'qrcode', TIMESTAMPTZ '2026-10-24 15:55:00-03'),
  (NULL, '[TESTE] Visitante 12', 'Cabo Frio',            'RJ', 'qrcode', TIMESTAMPTZ '2026-10-31 09:35:00-03'),
  (NULL, '[TESTE] Visitante 13', 'Arraial do Cabo',      'RJ', 'qrcode', TIMESTAMPTZ '2026-11-07 10:25:00-03'),
  (NULL, '[TESTE] Visitante 14', 'Rio de Janeiro',       'RJ', 'qrcode', TIMESTAMPTZ '2026-11-08 13:15:00-03');
