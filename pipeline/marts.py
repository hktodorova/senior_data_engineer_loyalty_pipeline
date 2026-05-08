from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.config import MARTS_DIR


def _points_for_amount(amount: float, thresholds: "pd.DataFrame | None" = None) -> float:
    """Return points awarded for a given order amount based on threshold table."""
    if thresholds is None:
        from pipeline.config import RAW_DIR
        thresholds = pd.read_csv(RAW_DIR / "points_thresholds.csv")
    if pd.isna(amount):
        return 0
    match = thresholds[
        (thresholds["min_amount"] <= amount)
        & (
            thresholds["max_amount"].isna()
            | (amount <= thresholds["max_amount"])
        )
    ]
    if match.empty:
        return 0
    return float(match.sort_values("min_amount").iloc[-1]["points_awarded"])


def build_marts(stg: dict[str, pd.DataFrame], marts_dir: Path = MARTS_DIR) -> dict[str, pd.DataFrame]:
    """Build business-ready mart tables."""
    marts_dir.mkdir(parents=True, exist_ok=True)

    stg_orders_master = stg["stg_orders_master"]
    stg_order_details = stg["stg_order_details"]
    stg_payments = stg["stg_payments"]
    stg_customers = stg["stg_customers"]
    stg_customer_cards = stg["stg_customer_cards"]
    stg_products = stg["stg_products"]
    stg_card_points_ledger = stg["stg_card_points_ledger"]
    stg_points_thresholds = stg["stg_points_thresholds"]

    # Dimensions
    dim_customers = stg_customers.copy()
    dim_products = stg_products.copy()

    # fact_order_lines: one row per order line
    fact_order_lines = stg_order_details.merge(
        stg_products[["product_id", "product_name", "category"]],
        on="product_id",
        how="left",
    )
    fact_order_lines["line_gross"] = fact_order_lines["quantity"] * fact_order_lines["unit_price"]
    fact_order_lines["line_net"] = fact_order_lines["line_gross"] * (
        1 - fact_order_lines["discount_pct"] / 100
    )
    fact_order_lines["has_valid_product"] = fact_order_lines["product_name"].notna()
    fact_order_lines = fact_order_lines.rename(columns={"category": "product_category"})
    fact_order_lines = fact_order_lines[[
        "order_id", "line_id", "product_id", "quantity", "unit_price", "discount_pct",
        "line_gross", "line_net", "has_valid_product", "product_category",
    ]]

    # fact_payments: one row per payment event
    fact_payments = stg_payments.copy()
    fact_payments["is_successful_payment"] = fact_payments["payment_status"] == "success"
    fact_payments["is_refund"] = (
        (fact_payments["payment_status"] == "refunded")
        | (fact_payments["payment_type"] == "refund")
    )
    fact_payments["is_pending"] = fact_payments["payment_status"] == "pending"
    fact_payments["is_failed"] = fact_payments["payment_status"] == "failed"
    fact_payments["is_points_payment"] = fact_payments["payment_type"].isin(["points", "loyalty_card"])
    fact_payments["is_installment_payment"] = fact_payments["payment_type"] == "installment"
    fact_payments["cash_collected_amount"] = np.where(
        fact_payments["is_successful_payment"] & (fact_payments["payment_amount"] > 0),
        fact_payments["payment_amount"],
        0,
    )
    fact_payments["refund_amount"] = np.where(
        fact_payments["is_refund"],
        fact_payments["payment_amount"].abs(),
        0.0,
    )
    fact_payments = fact_payments[[
        "payment_id", "order_id", "payment_datetime", "payment_type", "payment_status",
        "payment_amount", "card_id", "points_used",
        "is_successful_payment", "is_refund", "is_pending", "is_failed",
        "is_points_payment", "is_installment_payment",
        "cash_collected_amount", "refund_amount",
    ]]

    # Order-level expected amount from lines
    order_amounts = (
        fact_order_lines.groupby("order_id", as_index=False)["line_net"]
        .sum()
        .rename(columns={"line_net": "order_expected_amount"})
    )

    # Payment aggregates per order
    payment_aggregates = (
        fact_payments.groupby("order_id", as_index=False)
        .agg(
            total_cash_collected_amount=("cash_collected_amount", "sum"),
            total_refund_amount=("refund_amount", "sum"),
            points_used=("points_used", "sum"),
            payment_event_count=("payment_id", "count"),
            installment_event_count=("is_installment_payment", "sum"),
            has_successful_payment=("is_successful_payment", "any"),
            has_pending_payment=("is_pending", "any"),
        )
    )

    latest_payment_status = (
        fact_payments.sort_values(
            ["order_id", "payment_datetime", "payment_id"],
            na_position="last",
        )
        .groupby("order_id", as_index=False)["payment_status"]
        .last()
        .rename(columns={"payment_status": "latest_payment_status"})
    )

    # fact_orders: one row per order
    fact_orders = stg_orders_master.merge(
        stg_customers[["customer_id", "segment"]].rename(columns={"segment": "customer_segment"}),
        on="customer_id",
        how="left",
    )
    fact_orders = fact_orders.merge(order_amounts, on="order_id", how="left")
    fact_orders = fact_orders.merge(payment_aggregates, on="order_id", how="left")
    fact_orders = fact_orders.merge(latest_payment_status, on="order_id", how="left")

    for col in [
        "order_expected_amount", "total_cash_collected_amount", "total_refund_amount",
        "points_used", "payment_event_count", "installment_event_count",
    ]:
        fact_orders[col] = fact_orders[col].fillna(0)
    for col in ["has_successful_payment", "has_pending_payment"]:
        fact_orders[col] = fact_orders[col].where(
            fact_orders[col].notna(),
            False,
        ).astype(bool)

    fact_orders["net_collected_amount"] = (
        fact_orders["total_cash_collected_amount"] - fact_orders["total_refund_amount"]
    )
    fact_orders["has_customer"] = fact_orders["customer_id"].isin(stg_customers["customer_id"])
    fact_orders["has_any_payment"] = fact_orders["payment_event_count"] > 0
    fact_orders["has_refund"] = fact_orders["total_refund_amount"] > 0
    fact_orders["is_fully_paid"] = (
        (fact_orders["net_collected_amount"] >= fact_orders["order_expected_amount"])
        & (fact_orders["order_expected_amount"] > 0)
    )
    fact_orders["is_partially_paid"] = (
        (fact_orders["net_collected_amount"] > 0)
        & (fact_orders["net_collected_amount"] < fact_orders["order_expected_amount"])
    )
    fact_orders["is_overpaid"] = (
        (fact_orders["net_collected_amount"] > fact_orders["order_expected_amount"])
        & (fact_orders["order_expected_amount"] > 0)
    )
    fact_orders["is_valid_revenue"] = (
        (fact_orders["order_status"] == "paid")
        & fact_orders["has_successful_payment"]
        & (fact_orders["net_collected_amount"] > 0)
    )
    fact_orders = fact_orders[[
        "order_id", "customer_id", "order_date", "order_status", "sales_channel", "currency",
        "customer_segment", "order_expected_amount",
        "total_cash_collected_amount", "total_refund_amount", "net_collected_amount",
        "points_used", "payment_event_count", "installment_event_count", "latest_payment_status",
        "has_customer", "has_any_payment", "has_successful_payment", "has_pending_payment",
        "has_refund", "is_fully_paid", "is_partially_paid", "is_overpaid", "is_valid_revenue",
    ]]

    # fact_card_points_ledger: raw ledger + threshold-based computed earn events
    active_cards = stg_customer_cards.loc[
        stg_customer_cards["card_status"] == "active",
        ["card_id", "customer_id", "card_status"],
    ].copy()

    eligible_orders = fact_orders.loc[
        fact_orders["is_valid_revenue"],
        ["order_id", "customer_id", "order_date", "order_expected_amount"],
    ].merge(active_cards, on="customer_id", how="inner")

    computed_earn = eligible_orders.copy()
    computed_earn["points_delta"] = computed_earn["order_expected_amount"].apply(
        lambda amt: _points_for_amount(amt, stg_points_thresholds)
    )
    computed_earn = computed_earn[computed_earn["points_delta"] > 0].copy()
    computed_earn["event_datetime"] = computed_earn["order_date"]
    computed_earn["event_type"] = "earn"
    computed_earn["ledger_source"] = "computed_threshold"
    computed_earn = computed_earn[[
        "order_id", "card_id", "event_datetime", "event_type", "points_delta", "ledger_source"
    ]]

    raw_ledger = stg_card_points_ledger.copy()
    raw_ledger["ledger_source"] = "raw"

    raw_earn_keys = raw_ledger.loc[
        raw_ledger["event_type"].eq("earn") & raw_ledger["order_id"].notna(),
        ["card_id", "order_id"],
    ].drop_duplicates()

    if not computed_earn.empty and not raw_earn_keys.empty:
        computed_earn = computed_earn.merge(
            raw_earn_keys.assign(_already_in_raw=True),
            on=["card_id", "order_id"],
            how="left",
        )
        computed_earn = computed_earn[computed_earn["_already_in_raw"].isna()].drop(columns="_already_in_raw")

    fact_card_points_ledger = pd.concat([raw_ledger, computed_earn], ignore_index=True, sort=False)
    fact_card_points_ledger = fact_card_points_ledger.merge(
        stg_customer_cards[["card_id", "customer_id", "card_status"]],
        on="card_id",
        how="left",
        suffixes=("", "_card"),
    )
    if "customer_id_card" in fact_card_points_ledger.columns:
        fact_card_points_ledger["customer_id"] = fact_card_points_ledger["customer_id"].fillna(
            fact_card_points_ledger["customer_id_card"]
        )
        fact_card_points_ledger = fact_card_points_ledger.drop(columns=["customer_id_card"])
    fact_card_points_ledger["is_valid_card"] = fact_card_points_ledger["customer_id"].notna()

    marts = {
        "dim_customers": dim_customers,
        "dim_products": dim_products,
        "fact_order_lines": fact_order_lines,
        "fact_payments": fact_payments,
        "fact_orders": fact_orders,
        "fact_card_points_ledger": fact_card_points_ledger,
    }

    for name, df in marts.items():
        df.to_csv(marts_dir / f"{name}.csv", index=False)

    return marts
