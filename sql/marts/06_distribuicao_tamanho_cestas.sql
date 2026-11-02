-- Distribuicao de pedidos segundo a quantidade de itens na cesta.
WITH itens AS (
    SELECT order_id FROM refined.itens_pedido_prior
    UNION ALL
    SELECT order_id FROM refined.itens_pedido_treino
),
cestas AS (
    SELECT order_id, COUNT(*) AS itens_por_pedido
    FROM itens
    GROUP BY order_id
),
distribuicao AS (
    SELECT itens_por_pedido, COUNT(*) AS quantidade_pedidos
    FROM cestas
    GROUP BY itens_por_pedido
)
SELECT
    itens_por_pedido,
    quantidade_pedidos,
    ROUND(
        quantidade_pedidos * 100.0 / SUM(quantidade_pedidos) OVER (),
        2
    ) AS percentual_pedidos
FROM distribuicao
ORDER BY itens_por_pedido
