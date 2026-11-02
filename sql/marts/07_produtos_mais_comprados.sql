-- Produtos mais frequentes nos itens prior e train, com alcance e recompra.
WITH itens AS (
    SELECT order_id, product_id, reordered
    FROM refined.itens_pedido_prior
    UNION ALL
    SELECT order_id, product_id, reordered
    FROM refined.itens_pedido_treino
)
SELECT
    p.product_id,
    p.product_name,
    COUNT(*) AS vezes_comprado,
    COUNT(DISTINCT i.order_id) AS pedidos_com_produto,
    ROUND(AVG(i.reordered) * 100, 2) AS percentual_recomprado
FROM itens i
JOIN refined.produtos p USING (product_id)
GROUP BY p.product_id, p.product_name
ORDER BY vezes_comprado DESC, p.product_id
LIMIT 20
