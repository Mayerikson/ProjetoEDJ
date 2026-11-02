-- Itens, participacao e recompra por departamento.
WITH itens AS (
    SELECT order_id, product_id, reordered
    FROM refined.itens_pedido_prior
    UNION ALL
    SELECT order_id, product_id, reordered
    FROM refined.itens_pedido_treino
),
departamentos AS (
    SELECT
        d.department_id,
        d.department,
        COUNT(*) AS quantidade_itens,
        COUNT(DISTINCT i.order_id) AS pedidos_com_itens,
        AVG(i.reordered) AS taxa_recompra
    FROM itens i
    JOIN refined.produtos p USING (product_id)
    JOIN refined.departamentos d USING (department_id)
    GROUP BY d.department_id, d.department
)
SELECT
    department_id,
    department,
    quantidade_itens,
    pedidos_com_itens,
    ROUND(quantidade_itens * 100.0 / SUM(quantidade_itens) OVER (), 2)
        AS percentual_dos_itens,
    ROUND(taxa_recompra * 100, 2) AS percentual_recomprado
FROM departamentos
ORDER BY quantidade_itens DESC, department_id
