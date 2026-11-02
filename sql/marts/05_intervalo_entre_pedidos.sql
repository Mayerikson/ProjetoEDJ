-- Frequencia dos intervalos observados; NULL representa o primeiro pedido.
SELECT
    days_since_prior_order AS dias_desde_pedido_anterior,
    COUNT(*) AS quantidade_pedidos
FROM refined.pedidos
WHERE eval_set IN ('prior', 'train')
GROUP BY days_since_prior_order
ORDER BY days_since_prior_order NULLS FIRST
