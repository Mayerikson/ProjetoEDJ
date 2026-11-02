-- Recompra por posicao em que o produto foi adicionado ao carrinho.
WITH itens AS (
    SELECT add_to_cart_order, reordered
    FROM refined.itens_pedido_prior
    UNION ALL
    SELECT add_to_cart_order, reordered
    FROM refined.itens_pedido_treino
)
SELECT
    add_to_cart_order AS posicao_no_carrinho,
    COUNT(*) AS quantidade_itens,
    ROUND(AVG(reordered) * 100, 2) AS percentual_recomprado
FROM itens
GROUP BY add_to_cart_order
ORDER BY add_to_cart_order
