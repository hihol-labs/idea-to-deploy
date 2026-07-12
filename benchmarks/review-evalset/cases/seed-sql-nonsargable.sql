-- отчёт по контрагентам
SELECT id, name FROM counterparties
WHERE lower(regexp_replace(btrim(name), '\s+', ' ', 'g')) = $1
ORDER BY id;
