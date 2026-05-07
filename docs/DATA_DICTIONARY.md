# Data Dictionary

## customers.csv
customer_id, customer_name, segment, country, signup_date, email

## customer_cards.csv
card_id, customer_id, card_created_at, card_status

## products.csv
product_id, product_name, category, standard_price, is_active

## orders_master.csv
order_id, customer_id, order_date, order_status, sales_channel, currency

## order_details.csv
order_id, line_id, product_id, quantity, unit_price, discount_pct

## payments.csv
payment_id, order_id, payment_datetime, payment_type, payment_status, payment_amount, card_id, points_used

## points_thresholds.csv
threshold_id, min_amount, max_amount, points_awarded

## card_points_ledger.csv
ledger_id, card_id, order_id, event_datetime, event_type, points_delta
