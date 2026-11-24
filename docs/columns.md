# Kolumny wejścia i wyniku

Wszystkie kwoty w zł bez VAT (cena brutto po rabacie / 1,23), chyba że opis mówi inaczej.

## Wejście: tabele Data-Generatora v1.7.1

| Tabela | Kolumny, które czyta projekt |
|---|---|
| `product_data` | `product_id`, `product_name`, `color`, `category`, `subcategory`, `product_type`, `brand`, `net_purchase_price` (koszt zakupu netto), `sales_price_gross` (cena dziś), `parcel_size` (small, medium, large, bulky) |
| `order_data` | `order_id`, `order_line_id`, `order_date`, `product_id`, `quantity`, `unit_price_gross` (cena z cennika w dniu zamówienia), `discount_rate`, `payment_method`, `payment_provider`, `delivery_method`, `channel`, `order_status`, `is_fraud`, `affiliate_commission` (prowizja zapłacona sieci partnerskiej, już po zwrotach) |
| `shipment_data` | `shipment_id`, `order_id`, `delivery_method`, `is_bulky`, `shipping_cost` (opłata klienta za dostawę, brutto), `parcel_size`, `carrier_cost` (koszt przewoźnika dla sklepu) |
| `return_data` | `return_id`, `order_id`, `order_line_id`, `product_id`, `returned_quantity`, `return_reason`, `refund_amount` (zwrot pieniędzy, brutto), `return_status` (refunded, rejected), `return_shipping_cost`, `handling_cost`, `written_off_quantity`, `write_off_cost` |
| `payment_data` | `payment_id`, `order_id`, `payment_amount`, `fee_rate`, `fixed_fee`, `payment_fee` (opłata operatora płatności) |

Kolumny „net” z danych nie są używane: przychód netto liczy się z ceny brutto i stawki VAT z ustawień generatora.

## Wynik: `output/product_margins.csv`

Jeden wiersz na produkt, który miał choć jedną linię zamówienia (bez zamówień oznaczonych jako oszustwa).

| Kolumna | Znaczenie |
|---|---|
| `units` | sztuki w zamówieniach dostarczonych albo zwróconych (anulowane i nieopłacone mają 0) |
| `units_refunded`, `units_written_off` | sztuki zwrócone z oddaniem pieniędzy; z nich sztuki do odpisu |
| `list_revenue` | sztuki × cena z cennika w dniu zamówienia |
| `discount` | rabaty na liniach |
| `purchase_cost` | sztuki × koszt zakupu |
| `refund` | zwrócone pieniądze |
| `restocked_cost` | koszt zakupu zwróconych sztuk, które wróciły na stan |
| `write_off_cost`, `return_shipping_cost`, `return_handling_cost` | odpis, etykieta zwrotna opłacona przez sklep, obsługa zwrotu |
| `carrier_cost`, `delivery_fee` | część kosztu przewoźnika i opłaty klienta za dostawę przypadająca na produkt (podział według wagi paczki) |
| `payment_fee` | część opłaty za płatność przypadająca na produkt (podział według wartości linii; także zamówienia anulowane i nieudane) |
| `commission` | prowizja afiliacyjna |
| `shipped_lines`, `free_delivery_lines` | linie wysłane; z nich linie z darmową dostawą |
| `list_margin` | marża z cennika: `list_revenue − purchase_cost` |
| `returns` | `refund − restocked_cost + write_off_cost + return_shipping_cost + return_handling_cost` |
| `shipping` | `carrier_cost − delivery_fee` |
| `payment` | `payment_fee` |
| `true_margin` | marża na czysto: `list_margin − discount − returns − shipping − payment − commission` |
| `net_revenue` | przychód netto: `list_revenue − discount − refund` |
| `list_margin_rate`, `true_margin_rate`, `return_rate` | `list_margin / list_revenue`, `true_margin / net_revenue`, `units_refunded / units` |

## Wynik: `output/loss_making_bestsellers.csv`

Kolumny jak wyżej, tylko dla stratnych bestsellerów, oraz:

| Kolumna | Znaczenie |
|---|---|
| `revenue_rank` | miejsce według przychodu netto (1 = najwyższy) |
| `driver` | koszt, który zabrał najwięcej (`price_list`, gdy marża z cennika jest zerowa albo ujemna) |
| `break_even_rise`, `break_even_rise_rate` | podwyżka ceny brutto na sztuce, przy której produkt wychodzi na zero, i jej udział w cenie |
| `break_even_discount_rate` | największy średni rabat, przy którym produkt wychodzi na zero |
| `free_delivery_share`, `category_return_rate`, `discount_rate` | udział linii z darmową dostawą, odsetek zwrotów w kategorii, średni rabat |
| `move` | `price` (zmień cenę), `free_shipping` (bez darmowej dostawy), `delist` (wycofaj) |
| `reason` | powód i ruch jednym zdaniem |
