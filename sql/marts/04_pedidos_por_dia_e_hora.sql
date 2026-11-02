-- Distribuicao conjunta de pedidos por dia da semana e hora.
SELECT
    order_dow AS dia_semana,
    order_hour_of_day AS hora,
    COUNT(*) AS quantidade_pedidos
FROM refined.pedidos
WHERE eval_set IN ('prior', 'train')
GROUP BY order_dow, order_hour_of_day
ORDER BY order_dow, order_hour_of_day
