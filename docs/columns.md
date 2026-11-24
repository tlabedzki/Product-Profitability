# Input and output columns

All amounts are in PLN without VAT (gross price after discount / 1.23) unless the description says otherwise.

## Input: Data-Generator v1.7.1 tables

| Table | Columns the project reads |
|---|---|
| `product_data` | `product_id`, `product_name`, `color`, `category`, `subcategory`, `product_type`, `brand`, `net_purchase_price` (purchase cost without VAT), `sales_price_gross` (today's price), `parcel_size` (small, medium, large, bulky) |
| `order_data` | `order_id`, `order_line_id`, `order_date`, `product_id`, `quantity`, `unit_price_gross` (price-list price on the order day), `discount_rate`, `payment_method`, `payment_provider`, `delivery_method`, `channel`, `order_status`, `is_fraud`, `affiliate_commission` (commission paid to the affiliate network, after returns) |
| `shipment_data` | `shipment_id`, `order_id`, `delivery_method`, `is_bulky`, `shipping_cost` (delivery fee paid by the customer, gross), `parcel_size`, `carrier_cost` (what the carrier charges the shop) |
| `return_data` | `return_id`, `order_id`, `order_line_id`, `product_id`, `returned_quantity`, `return_reason`, `refund_amount` (money refunded, gross), `return_status` (refunded, rejected), `return_shipping_cost`, `handling_cost`, `written_off_quantity`, `write_off_cost` |
| `payment_data` | `payment_id`, `order_id`, `payment_amount`, `fee_rate`, `fixed_fee`, `payment_fee` (payment operator fee) |

The "net" columns of the data are not used: net revenue comes from the gross price and the VAT rate in the
generator's settings.

## Output: `output/product_margins.csv`

One row per product with at least one order line (orders labelled as fraud left out).

| Column | Meaning |
|---|---|
| `units` | units in delivered or returned orders (cancelled and unpaid orders count 0) |
| `units_refunded`, `units_written_off` | units returned with a refund; of those, the units written off |
| `list_revenue` | units × price-list price on the order day |
| `discount` | line discounts |
| `purchase_cost` | units × purchase cost |
| `refund` | money refunded |
| `restocked_cost` | purchase cost of the returned units that went back into stock |
| `write_off_cost`, `return_shipping_cost`, `return_handling_cost` | write-off, return label paid by the shop, return handling |
| `carrier_cost`, `delivery_fee` | the product's share of the carrier cost and of the delivery fee paid by the customer (split by parcel weight) |
| `payment_fee` | the product's share of the payment fee (split by line value; cancelled and failed orders included) |
| `commission` | affiliate commission |
| `shipped_lines`, `free_delivery_lines` | lines shipped; of those, lines with free delivery |
| `list_margin` | price-list margin: `list_revenue − purchase_cost` |
| `returns` | `refund − restocked_cost + write_off_cost + return_shipping_cost + return_handling_cost` |
| `shipping` | `carrier_cost − delivery_fee` |
| `payment` | `payment_fee` |
| `true_margin` | true margin: `list_margin − discount − returns − shipping − payment − commission` |
| `net_revenue` | net revenue: `list_revenue − discount − refund` |
| `list_margin_rate`, `true_margin_rate`, `return_rate` | `list_margin / list_revenue`, `true_margin / net_revenue`, `units_refunded / units` |

## Output: `output/loss_making_bestsellers.csv`

The columns above, only for the loss-making bestsellers, and:

| Column | Meaning |
|---|---|
| `revenue_rank` | rank by net revenue (1 = highest) |
| `driver` | the cost that took the most (`price_list` when the price-list margin is zero or negative) |
| `break_even_rise`, `break_even_rise_rate` | gross price rise per unit at which the product breaks even, and its share of the price (after the discount and the fees that grow with the price) |
| `break_even_discount_rate` | the largest average discount at which the product still breaks even |
| `free_delivery_share`, `category_return_rate`, `discount_rate` | share of lines shipped free, return rate of the category, average discount |
| `move` | `price` (change the price), `free_shipping` (end free delivery), `delist` (delist) |
| `reason` | reason and move in one sentence |
