-- Volume de pedidos observados por dia da semana (0 a 6).
SELECT
    order_dow AS dia_semana,
    COUNT(*) AS quantidade_pedidos
FROM refined.pedidos
WHERE eval_set IN ('prior', 'train')
GROUP BY order_dow
ORDER BY order_dow
