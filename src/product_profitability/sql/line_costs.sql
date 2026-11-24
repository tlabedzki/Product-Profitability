-- Revenue and selling costs of every order line, in PLN without VAT.
-- Order-level costs are spread over the lines of the order:
--   carrier cost and the delivery fee paid by the customer by parcel weight (units x typical carrier cost of the
--   product's parcel size, from one-unit parcels), payment fees by the line value.
-- Inputs registered by margin.py: products, orders, shipments, returns, payments; parameter $vat.
WITH lines AS (
    SELECT o.order_id, o.order_line_id, o.product_id, o.quantity, o.unit_price_gross, o.discount_rate,
           o.delivery_method, o.affiliate_commission,
           o.order_status IN ('delivered', 'returned') AS realised,
           p.net_purchase_price, p.parcel_size,
           o.quantity * o.unit_price_gross * (1 - o.discount_rate) AS value_gross
    FROM orders AS o
    JOIN products AS p USING (product_id)
    WHERE o.order_id NOT IN (SELECT order_id FROM orders WHERE is_fraud)
),
single_unit AS (
    SELECT s.delivery_method, any_value(l.parcel_size) AS parcel_size, s.carrier_cost
    FROM shipments AS s
    JOIN lines AS l USING (order_id)
    GROUP BY s.order_id, s.delivery_method, s.carrier_cost
    HAVING count(*) = 1 AND sum(l.quantity) = 1
),
size_by_method AS (
    SELECT delivery_method, parcel_size, median(carrier_cost) AS size_weight
    FROM single_unit GROUP BY ALL
),
size_overall AS (
    SELECT parcel_size, median(carrier_cost) AS size_weight
    FROM single_unit GROUP BY ALL
),
weighted AS (
    -- A size with no one-unit parcels (or a free one) falls back to the size overall, then to all parcels.
    SELECT l.*,
           l.quantity * coalesce(nullif(m.size_weight, 0), nullif(a.size_weight, 0),
                                 nullif((SELECT median(carrier_cost) FROM single_unit), 0), 1.0) AS parcel_weight
    FROM lines AS l
    LEFT JOIN size_by_method AS m USING (delivery_method, parcel_size)
    LEFT JOIN size_overall AS a USING (parcel_size)
),
shares AS (
    SELECT *,
           CASE WHEN sum(parcel_weight) OVER (PARTITION BY order_id) > 0
                THEN parcel_weight / sum(parcel_weight) OVER (PARTITION BY order_id)
                ELSE 1.0 / count(*) OVER (PARTITION BY order_id) END AS shipping_share,
           CASE WHEN sum(value_gross) OVER (PARTITION BY order_id) > 0
                THEN value_gross / sum(value_gross) OVER (PARTITION BY order_id)
                ELSE 1.0 / count(*) OVER (PARTITION BY order_id) END AS payment_share
    FROM weighted
),
line_returns AS (
    SELECT order_line_id,
           sum(CASE WHEN return_status = 'refunded' THEN refund_amount ELSE 0 END) AS refund_gross,
           sum(CASE WHEN return_status = 'refunded' THEN returned_quantity ELSE 0 END) AS units_refunded,
           sum(written_off_quantity) AS units_written_off,
           sum(write_off_cost) AS write_off_cost,
           sum(return_shipping_cost) AS return_shipping_cost,
           sum(handling_cost) AS handling_cost
    FROM returns GROUP BY order_line_id
)
SELECT x.order_id, x.order_line_id, x.product_id,
       CASE WHEN x.realised THEN x.quantity ELSE 0 END AS units,
       coalesce(r.units_refunded, 0) AS units_refunded,
       coalesce(r.units_written_off, 0) AS units_written_off,
       CASE WHEN x.realised THEN x.quantity * x.unit_price_gross / (1 + $vat) ELSE 0 END AS list_revenue,
       CASE WHEN x.realised THEN x.quantity * x.unit_price_gross * x.discount_rate / (1 + $vat) ELSE 0 END
           AS discount,
       CASE WHEN x.realised THEN x.quantity * x.net_purchase_price ELSE 0 END AS purchase_cost,
       coalesce(r.refund_gross, 0) / (1 + $vat) AS refund,
       coalesce(r.units_refunded, 0) * x.net_purchase_price AS restocked_cost,
       coalesce(r.write_off_cost, 0) AS write_off_cost,
       coalesce(r.return_shipping_cost, 0) AS return_shipping_cost,
       coalesce(r.handling_cost, 0) AS return_handling_cost,
       coalesce(s.carrier_cost, 0) * x.shipping_share AS carrier_cost,
       coalesce(s.shipping_cost, 0) / (1 + $vat) * x.shipping_share AS delivery_fee,
       coalesce(pay.payment_fee, 0) * x.payment_share AS payment_fee,
       (s.order_id IS NOT NULL)::INTEGER AS shipped_lines,
       (s.order_id IS NOT NULL AND s.shipping_cost = 0)::INTEGER AS free_delivery_lines,
       x.affiliate_commission AS commission
FROM shares AS x
LEFT JOIN line_returns AS r USING (order_line_id)
LEFT JOIN shipments AS s USING (order_id)
LEFT JOIN payments AS pay USING (order_id)
ORDER BY x.order_line_id
