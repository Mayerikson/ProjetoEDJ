-- Itens, pedidos distintos e recompra por corredor (aisle).
WITH itens AS (
    SELECT order_id, product_id, reordered
    FROM refined.itens_pedido_prior
    UNION ALL
    SELECT order_id, product_id, reordered
    FROM refined.itens_pedido_treino
)
SELECT
    c.aisle_id,
    c.aisle,
    COUNT(*) AS quantidade_itens,
    COUNT(DISTINCT i.order_id) AS pedidos_com_itens,
    ROUND(AVG(i.reordered) * 100, 2) AS percentual_recomprado
FROM itens i
JOIN refined.produtos p USING (product_id)
JOIN refined.corredores c USING (aisle_id)
GROUP BY c.aisle_id, c.aisle
ORDER BY quantidade_itens DESC, c.aisle_id
