-- SAP-Charitas | Consultas do dashboard do administrador (RF9)
-- Todas contam a tabela "visita" e agrupam no horario de Brasilia
-- (sem o AT TIME ZONE, uma visita as 22h de 31/10 cairia em novembro).

-- 1) Visitas por mes
SELECT date_trunc('month', registrada_em AT TIME ZONE 'America/Sao_Paulo')::date AS mes,
       COUNT(*) AS visitas
FROM visita
GROUP BY mes
ORDER BY mes;

-- 2) Mes com mais visitas
SELECT date_trunc('month', registrada_em AT TIME ZONE 'America/Sao_Paulo')::date AS mes,
       COUNT(*) AS visitas
FROM visita
GROUP BY mes
ORDER BY visitas DESC, mes DESC
LIMIT 1;

-- 3) Cidades de origem dos visitantes (top 10)
SELECT COALESCE(cidade, 'Não informada') AS cidade, estado, COUNT(*) AS visitas
FROM visita
GROUP BY cidade, estado
ORDER BY visitas DESC, cidade
LIMIT 10;

-- 4) Visitas por evento (as visitas gerais aparecem como "Visita geral")
SELECT COALESCE(e.titulo, 'Visita geral') AS origem, COUNT(*) AS visitas
FROM visita v
LEFT JOIN evento e ON e.id = v.evento_id
GROUP BY origem
ORDER BY visitas DESC;

-- 5) Taxa de comparecimento dos agendamentos (por evento)
SELECT e.titulo,
       COUNT(a.id)                                           AS agendados,
       COUNT(a.id) FILTER (WHERE a.presente)                 AS presentes,
       ROUND(100.0 * COUNT(a.id) FILTER (WHERE a.presente) / NULLIF(COUNT(a.id), 0), 1) AS taxa_pct
FROM evento e
LEFT JOIN agendamento a ON a.evento_id = e.id
WHERE e.ativo
GROUP BY e.id, e.titulo
ORDER BY e.data_evento;

-- 6) Dia da semana mais movimentado (0 = domingo ... 6 = sabado)
SELECT EXTRACT(DOW FROM registrada_em AT TIME ZONE 'America/Sao_Paulo')::int AS dia_semana,
       COUNT(*) AS visitas
FROM visita
GROUP BY dia_semana
ORDER BY visitas DESC;

-- 7) Como a presenca foi registrada (QR code x marcada pelo administrador)
SELECT metodo, COUNT(*) AS visitas
FROM visita
GROUP BY metodo;
