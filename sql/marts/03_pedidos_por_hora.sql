-- Volume de pedidos observados por hora do dia (0 a 23).
SELECT
    order_hour_of_day AS hora,
    COUNT(*) AS quantidade_pedidos
FROM refined.pedidos
WHERE eval_set IN ('prior', 'train')
GROUP BY order_hour_of_day
ORDER BY order_hour_of_day
