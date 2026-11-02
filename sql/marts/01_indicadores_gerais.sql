-- KPIs gerais. Itens combinam prior e train; pedidos test nao tem itens rotulados.
WITH itens AS (
    SELECT order_id, product_id, reordered
    FROM refined.itens_pedido_prior
    UNION ALL
    SELECT order_id, product_id, reordered
    FROM refined.itens_pedido_treino
),
cestas AS (
    SELECT order_id, COUNT(*) AS itens_por_pedido
    FROM itens
    GROUP BY order_id
)
SELECT
    (
        SELECT COUNT(*)
        FROM refined.pedidos
        WHERE eval_set IN ('prior', 'train')
    ) AS total_pedidos,
    (
        SELECT COUNT(DISTINCT user_id)
        FROM refined.pedidos
        WHERE eval_set IN ('prior', 'train')
    ) AS total_usuarios,
    (SELECT COUNT(*) FROM itens) AS total_itens,
    (SELECT COUNT(DISTINCT product_id) FROM itens) AS produtos_comprados,
    (SELECT ROUND(AVG(reordered) * 100, 2) FROM itens) AS percentual_itens_recomprados,
    (SELECT ROUND(AVG(itens_por_pedido), 2) FROM cestas) AS media_itens_por_pedido
