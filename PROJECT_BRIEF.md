# Senior Data Engineer Project: Retail Orders, Payments & Loyalty Pipeline

## Context

You are building a production-grade retail data pipeline inspired by loyalty-card systems used by large store chains. The business sells orders with multiple order lines. Customers may or may not have loyalty cards. Customers can earn points based on order value and can later redeem points to pay for purchases. Payments can be cash, bank/card payment, loyalty-card payment, points payment, refund, or installment payment.

Your goal is to design and implement a reliable data pipeline that transforms messy raw data into clean staging tables, modeled fact/dimension tables, KPI outputs, and data quality reports.

## Raw data

Located in `data/raw/`:

- customers.csv
- customer_cards.csv
- products.csv
- orders_master.csv
- order_details.csv
- payments.csv
- points_thresholds.csv
- card_points_ledger.csv

## Important modeling rules

### Orders

`orders_master.csv` is the order header table. One valid row should represent one order.

`order_details.csv` is the order line table. One order may have many lines. The same product can appear multiple times in the same order. This is valid.

Do not deduplicate order details by `order_id + product_id`.

Calculate:

```text
line_gross = quantity * unit_price
line_net = line_gross * (1 - discount_pct / 100)
order_expected_amount = sum(line_net) per order_id
```

### Payments

Payments are events. One order can have multiple payment events.

Payment types:

```text
card, cash, installment, loyalty_card, points, refund
```

Payment statuses:

```text
success, failed, pending, refunded
```

Rules:

```text
success payment with positive amount adds collected cash
refund/refunded payment with negative amount reduces collected cash
failed or pending payments should not count as collected revenue
points payments may have payment_amount = 0 but points_used > 0
```

### Loyalty cards and points

A customer may or may not have a card.

Cards have statuses:

```text
active, inactive, blocked
```

Points thresholds are defined in `points_thresholds.csv`.

Points ledger is event-based:

```text
earn       -> positive points_delta
redeem     -> negative points_delta
refund     -> negative reversal
adjustment -> manual correction
```

Balance:

```text
points_balance = sum(points_delta) per card_id
```

## Required architecture

Implement:

```text
raw -> staging -> marts -> analytics -> data_quality
```

## Required outputs

Create:

```text
data/staging/stg_orders_master.csv
data/staging/stg_order_details.csv
data/staging/stg_payments.csv
data/staging/stg_customers.csv
data/staging/stg_customer_cards.csv
data/staging/stg_products.csv

data/marts/dim_customers.csv
data/marts/dim_products.csv
data/marts/fact_order_lines.csv
data/marts/fact_orders.csv
data/marts/fact_payments.csv
data/marts/fact_card_points_ledger.csv

data/analytics/kpi_summary.csv
data/analytics/revenue_by_day.csv
data/analytics/revenue_by_customer_segment.csv
data/analytics/loyalty_card_summary.csv

data/data_quality/data_quality_report.csv
```

## Staging requirements

### General

In staging:

```text
normalize data types
normalize string casing
remove technical duplicates
do not apply high-level KPI logic
preserve data quality signals
```

### stg_orders_master

```text
order_id -> numeric
customer_id -> numeric
order_date -> datetime
order_status -> lowercase + stripped
sales_channel -> lowercase + stripped
currency -> uppercase
deduplicate by order_id, keep last
drop rows where order_id or customer_id is missing
do not drop missing customer references here
```

### stg_order_details

```text
order_id -> numeric
line_id -> numeric
product_id -> uppercase + stripped
quantity -> numeric, fill missing with 1
unit_price -> numeric after removing " CHF"
discount_pct -> numeric, fill missing with 0
deduplicate exact technical duplicates
do not deduplicate by product_id
```

### stg_payments

```text
payment_id -> numeric
order_id -> numeric
payment_datetime -> datetime
payment_type -> lowercase + stripped
payment_status -> lowercase + stripped
payment_amount -> numeric, fill missing with 0
points_used -> numeric, fill missing with 0
card_id -> stripped + uppercase
deduplicate by payment_id
drop rows missing payment_id or order_id
```

### stg_customer_cards

```text
card_id -> stripped + uppercase
customer_id -> numeric
card_created_at -> datetime
card_status -> lowercase + stripped
deduplicate by card_id
drop missing card_id or customer_id
```

## Mart requirements

### fact_order_lines

One row per valid order line.

Fields:

```text
order_id, line_id, product_id, quantity, unit_price, discount_pct,
line_gross, line_net, has_valid_product, product_category
```

### fact_payments

One row per payment event.

Fields:

```text
payment_id, order_id, payment_datetime, payment_type, payment_status,
payment_amount, card_id, points_used, is_successful_payment, is_refund,
is_pending, is_failed, is_points_payment, is_installment_payment,
cash_collected_amount, refund_amount
```

Suggested rules:

```text
cash_collected_amount = payment_amount when payment_status = success and payment_amount > 0
refund_amount = abs(payment_amount) when payment_status = refunded OR payment_type = refund
```

### fact_orders

One row per order.

Required fields:

```text
order_id
customer_id
order_date
order_status
sales_channel
currency
customer_segment
order_expected_amount
total_cash_collected_amount
total_refund_amount
net_collected_amount
points_used
payment_event_count
installment_event_count
latest_payment_status
has_customer
has_any_payment
has_successful_payment
has_pending_payment
has_refund
is_fully_paid
is_partially_paid
is_overpaid
is_valid_revenue
```

Suggested logic:

```text
net_collected_amount = total_cash_collected_amount - total_refund_amount
is_fully_paid = net_collected_amount >= order_expected_amount
is_partially_paid = net_collected_amount > 0 AND net_collected_amount < order_expected_amount
is_overpaid = net_collected_amount > order_expected_amount
is_valid_revenue = order_status = paid AND has_successful_payment = true AND net_collected_amount > 0
```

## Loyalty rules

### Points earning

A customer earns points when:

```text
customer has an active card
order is valid revenue
order_expected_amount falls into a threshold
```

### Points redemption

A customer redeems points when:

```text
payment_type in ('points', 'loyalty_card')
points_used > 0
payment_status = success
```

End-of-period balance is acceptable. Exact balance-at-payment-time is a bonus.

## Data quality report

Create a table with:

```text
check_name
severity
failed_count
description
```

Required checks:

```text
duplicate_orders
duplicate_payment_ids
orders_without_customer
order_details_without_order
order_lines_with_invalid_product
payments_without_order
payments_with_invalid_card
payments_with_card_not_owned_by_customer
payments_using_inactive_or_blocked_card
orders_without_payment
cancelled_orders_with_successful_payment
paid_orders_without_successful_payment
orders_with_negative_expected_amount
orders_overpaid
points_used_without_card
points_ledger_invalid_card
negative_points_balance
```

## KPI requirements

Create `kpi_summary.csv`.

Required KPIs:

```text
total_orders
valid_revenue_orders
conversion_rate
total_expected_revenue
total_cash_collected
total_refunds
net_collected_revenue
avg_order_value
partial_payment_orders
overpaid_orders
cancelled_orders_with_payment
active_cards
points_earned
points_redeemed
points_liability
orders_paid_with_points
loyalty_revenue_share
```

Definitions:

```text
conversion_rate = valid_revenue_orders / total_orders
avg_order_value = net_collected_revenue / valid_revenue_orders
points_liability = total unused points balance
loyalty_revenue_share = revenue from orders linked to customers with active cards / total valid revenue
```

## Senior expectations

Your solution should show:

```text
clear separation of layers
idempotent output generation
deduplication based on correct business keys
join-key validation
handling one-to-many relationships
event-based payment processing
loyalty ledger thinking
data quality checks
KPI definitions
readable code organization
```

## Suggested script structure

```text
scripts/
  01_staging.py
  02_marts.py
  03_data_quality.py
  04_kpis.py
  run_pipeline.py
```

Or one file with functions:

```python
# load_raw_data()
# build_staging()
# build_marts()
# run_data_quality_checks()
# build_kpis()
# write_outputs()
```

## Bonus tasks

```text
1. Make the pipeline incremental using a last_processed_timestamp.
2. Add unit tests.
3. Add logging and runtime metrics.
4. Add schema validation.
5. Implement SCD Type 2 for customer segment changes.
6. Rewrite marts/KPIs in SQL.
7. Port the project to Spark.
8. Port the transformation layer to dbt.
```
