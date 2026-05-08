# Senior Data Engineer – Retail Orders, Payments & Loyalty Pipeline

A production-grade data pipeline that transforms messy raw retail data into clean staging tables, modeled fact/dimension tables, KPI outputs, and a data quality report.

---

## Quick start

```bash
pip install -e .
retail-pipeline
```

Requires Python 3.11+.

All outputs are written to `data/` and are fully idempotent – re-running overwrites everything cleanly.

---

## Project structure

```text
pipeline/
  __init__.py
  main.py
  staging.py
  marts.py
  analytics.py
  data_quality.py
  config.py
  logger.py

tests/
  test_marts.py
  test_revenue_logic.py
  test_order_status.py
  test_loyalty.py
  test_data_quality.py

data/
  raw/
  staging/
  marts/
  analytics/
  data_quality/

docs/
  DATA_DICTIONARY.md

README.md
requirements.txt
pyproject.toml
PROJECT_BRIEF.md
```

---

# Pipeline architecture

```text
raw -> staging -> marts -> analytics -> data_quality
```

---

## 1 · Raw layer (`data/raw/`)

Eight source files are provided with intentional production-style data issues:

| File                   | Description               |
| ---------------------- | ------------------------- |
| customers.csv          | Customer master table     |
| customer_cards.csv     | Loyalty cards             |
| products.csv           | Product catalog           |
| orders_master.csv      | Order headers             |
| order_details.csv      | Order lines               |
| payments.csv           | Payment events            |
| points_thresholds.csv  | Points earning thresholds |
| card_points_ledger.csv | Loyalty points ledger     |

Intentional issues include:

- duplicate order headers
- duplicate payment IDs
- orphan payments
- invalid products/cards
- inactive or blocked cards
- refund events
- failed → success payment retries

---

## 2 · Staging layer (`data/staging/`)

The staging layer performs:

- datatype normalization
- string casing normalization
- technical deduplication
- critical key cleanup
- preservation of data quality signals

No KPI logic is applied here.

### Generated staging tables

| Table                  | Description             |
| ---------------------- | ----------------------- |
| stg_orders_master      | Clean order headers     |
| stg_order_details      | Clean order lines       |
| stg_payments           | Clean payment events    |
| stg_customers          | Clean customers         |
| stg_customer_cards     | Clean loyalty cards     |
| stg_products           | Clean products          |
| stg_points_thresholds  | Clean points thresholds |
| stg_card_points_ledger | Clean points ledger     |

---

## 3 · Mart layer (`data/marts/`)

Business-ready analytical tables.

### Dimensions

| Table         | Description        |
| ------------- | ------------------ |
| dim_customers | Customer dimension |
| dim_products  | Product dimension  |

### Facts

| Table                   | Description                                     |
| ----------------------- | ----------------------------------------------- |
| fact_order_lines        | One row per order line                          |
| fact_payments           | One row per payment event                       |
| fact_orders             | One row per order                               |
| fact_card_points_ledger | Loyalty points ledger with computed earn events |

### Key calculated fields

#### fact_order_lines

```text
line_gross = quantity * unit_price
line_net = line_gross * (1 - discount_pct / 100)
```

#### fact_payments

```text
cash_collected_amount:
  payment_status = success
  AND payment_amount > 0

refund_amount:
  payment_status = refunded
  OR payment_type = refund
```

#### fact_orders

```text
net_collected_amount =
  total_cash_collected_amount - total_refund_amount

is_fully_paid =
  net_collected_amount >= order_expected_amount

is_partially_paid =
  net_collected_amount > 0
  AND net_collected_amount < order_expected_amount

is_overpaid =
  net_collected_amount > order_expected_amount

is_valid_revenue =
  order_status = paid
  AND has_successful_payment = true
  AND net_collected_amount > 0
```

---

## Loyalty points logic

### Points earning

A customer earns points when:

- the customer has an active loyalty card
- the order is valid revenue
- the order amount matches a threshold tier

Computed earn events are automatically generated and appended to the ledger.

### Points redemption

A customer redeems points when:

```text
payment_type in ('points', 'loyalty_card')
AND points_used > 0
AND payment_status = success
```

### Points balance

```text
points_balance = SUM(points_delta) per card_id
```

---

## 4 · Analytics layer (`data/analytics/`)

Generated outputs:

| File                            | Description                 |
| ------------------------------- | --------------------------- |
| kpi_summary.csv                 | Business KPI summary        |
| revenue_by_day.csv              | Revenue aggregated by day   |
| revenue_by_customer_segment.csv | Revenue by customer segment |
| loyalty_card_summary.csv        | Per-card loyalty summary    |

---

## 5 · Data quality layer (`data/data_quality/`)

`data_quality_report.csv` contains:

```text
check_name
severity
failed_count
description
```

Implemented checks include:

- duplicate_orders
- duplicate_payment_ids
- orders_without_customer
- order_details_without_order
- order_lines_with_invalid_product
- payments_without_order
- payments_with_invalid_card
- payments_with_card_not_owned_by_customer
- payments_using_inactive_or_blocked_card
- orders_without_payment
- cancelled_orders_with_successful_payment
- paid_orders_without_successful_payment
- orders_with_negative_expected_amount
- orders_overpaid
- points_used_without_card
- points_ledger_invalid_card
- negative_points_balance

---

## KPI summary (latest pipeline run)

| KPI                           | Value         |
| ----------------------------- | ------------- |
| total_orders                  | 1200          |
| valid_revenue_orders          | 777           |
| conversion_rate               | 64.75%        |
| total_expected_revenue        | CHF 2,008,332 |
| total_cash_collected          | CHF 1,980,528 |
| total_refunds                 | CHF 39,293    |
| net_collected_revenue         | CHF 1,941,235 |
| avg_order_value               | CHF 2,498     |
| partial_payment_orders        | 513           |
| overpaid_orders               | 334           |
| cancelled_orders_with_payment | 20            |
| active_cards                  | 140           |
| points_earned                 | 47,649        |
| points_redeemed               | 1,795         |
| points_liability              | 46,084        |
| orders_paid_with_points       | 22            |
| loyalty_revenue_share         | 56.92%        |

---

## Engineering decisions

### Correct handling of one-to-many relationships

The same product may appear multiple times in the same order.

The solution intentionally does NOT deduplicate order lines by:

```text
order_id + product_id
```

Only exact technical duplicates are removed.

### Event-based payment processing

Payments are modeled as events.

Multiple payment events per order are valid:

- retries
- partial payments
- refunds
- installments
- loyalty payments

### Idempotent outputs

Every pipeline run overwrites outputs safely.

### Separation of layers

The project cleanly separates:

- raw ingestion
- staging cleanup
- mart/business logic
- analytics
- data quality

---

## Senior-level concepts demonstrated

- data modeling
- fact/dimension architecture
- event-based payment processing
- join-key validation
- one-to-many relationship handling
- loyalty ledger modeling
- KPI engineering
- data quality checks
- idempotent pipelines
- pandas-based transformation pipelines
- modular pipeline architecture
- structured logging
- Python packaging and CLI execution

---

## Tests

Run the test suite:

```bash
pytest
```

Implemented tests cover:

- mart calculations
- KPI logic
- loyalty points logic
- revenue calculations
- data quality validation

---

## Possible future improvements

Potential extensions:

1. Incremental processing
2. Pandera schema validation
3. Runtime metrics and monitoring
4. SQL/dbt implementation
5. Spark implementation
6. SCD Type 2 customer tracking
7. Dockerization
8. CI/CD pipeline
9. Airflow orchestration
10. Cloud deployment
