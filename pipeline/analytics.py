from pathlib import Path

import pandas as pd

from pipeline.config import ANALYTICS_DIR


def build_analytics(
    marts: dict[str, pd.DataFrame],
    analytics_dir: Path = ANALYTICS_DIR,
) -> dict[str, pd.DataFrame]:
    """Build analytics-layer outputs: daily revenue, segment revenue, loyalty summary."""
    analytics_dir.mkdir(parents=True, exist_ok=True)

    fact_orders = marts["fact_orders"]
    fact_card_points_ledger = marts["fact_card_points_ledger"]

    # revenue_by_day
    rev_orders = fact_orders[fact_orders["is_valid_revenue"]].copy()
    rev_orders["order_date"] = pd.to_datetime(rev_orders["order_date"]).dt.date
    revenue_by_day = (
        rev_orders.groupby("order_date", as_index=False).agg(
            order_count=("order_id", "count"),
            total_expected_revenue=("order_expected_amount", "sum"),
            total_cash_collected=("total_cash_collected_amount", "sum"),
            total_refunds=("total_refund_amount", "sum"),
            net_collected_revenue=("net_collected_amount", "sum"),
        ).sort_values("order_date")
    )
    revenue_by_day.to_csv(analytics_dir / "revenue_by_day.csv", index=False)

    # revenue_by_customer_segment
    revenue_by_segment = (
        rev_orders.groupby("customer_segment", as_index=False).agg(
            order_count=("order_id", "count"),
            total_expected_revenue=("order_expected_amount", "sum"),
            net_collected_revenue=("net_collected_amount", "sum"),
            avg_order_value=("net_collected_amount", "mean"),
        ).sort_values("net_collected_revenue", ascending=False)
    )
    revenue_by_segment.to_csv(analytics_dir / "revenue_by_customer_segment.csv", index=False)

    # loyalty_card_summary – one row per card
    card_balance = (
        fact_card_points_ledger.groupby("card_id", as_index=False).agg(
            points_earned=("points_delta", lambda s: int(s[s > 0].sum())),
            points_redeemed=("points_delta", lambda s: int(s[s < 0].abs().sum())),
            points_balance=("points_delta", "sum"),
            transaction_count=("points_delta", "count"),
        )
    )
    card_meta = (
        fact_card_points_ledger[["card_id", "customer_id", "card_status"]]
        .drop_duplicates(subset="card_id")
    )
    loyalty_card_summary = card_balance.merge(card_meta, on="card_id", how="left")
    loyalty_card_summary.to_csv(analytics_dir / "loyalty_card_summary.csv", index=False)

    return {
        "revenue_by_day": revenue_by_day,
        "revenue_by_customer_segment": revenue_by_segment,
        "loyalty_card_summary": loyalty_card_summary,
    }


def build_kpis(
    marts: dict[str, pd.DataFrame],
    analytics: dict[str, pd.DataFrame],
    analytics_dir: Path = ANALYTICS_DIR,
) -> pd.DataFrame:
    """Compute all required KPIs and write kpi_summary.csv."""
    analytics_dir.mkdir(parents=True, exist_ok=True)

    fact_orders = marts["fact_orders"]
    fact_card_points_ledger = marts["fact_card_points_ledger"]

    total_orders = len(fact_orders)
    valid_revenue_orders = int(fact_orders["is_valid_revenue"].sum())
    conversion_rate = (valid_revenue_orders / total_orders) if total_orders > 0 else 0.0

    valid_orders = fact_orders[fact_orders["is_valid_revenue"]]
    total_expected_revenue = float(valid_orders["order_expected_amount"].sum())
    total_cash_collected = float(valid_orders["total_cash_collected_amount"].sum())
    total_refunds = float(valid_orders["total_refund_amount"].sum())
    net_collected_revenue = float(valid_orders["net_collected_amount"].sum())
    avg_order_value = (net_collected_revenue / valid_revenue_orders) if valid_revenue_orders > 0 else 0.0

    partial_payment_orders = int(fact_orders["is_partially_paid"].sum())
    overpaid_orders = int(fact_orders["is_overpaid"].sum())
    cancelled_orders_with_payment = int(
        ((fact_orders["order_status"] == "cancelled") & fact_orders["has_any_payment"]).sum()
    )

    active_cards = int(
        fact_card_points_ledger[fact_card_points_ledger["card_status"] == "active"]["card_id"].nunique()
    )

    points_earned = int(
        fact_card_points_ledger.loc[fact_card_points_ledger["points_delta"] > 0, "points_delta"].sum()
    )
    points_redeemed = int(
        fact_card_points_ledger.loc[fact_card_points_ledger["points_delta"] < 0, "points_delta"].abs().sum()
    )
    card_balance = fact_card_points_ledger.groupby("card_id")["points_delta"].sum()
    points_liability = int(card_balance[card_balance > 0].sum())

    orders_paid_with_points = int(
        ((fact_orders["points_used"] > 0) & fact_orders["is_valid_revenue"]).sum()
    )

    active_card_customers = (
        fact_card_points_ledger.loc[fact_card_points_ledger["card_status"] == "active", "customer_id"]
        .dropna().unique()
    )
    loyalty_valid_revenue = float(
        valid_orders.loc[valid_orders["customer_id"].isin(active_card_customers), "net_collected_amount"].sum()
    )
    loyalty_revenue_share = (
        (loyalty_valid_revenue / net_collected_revenue) if net_collected_revenue > 0 else 0.0
    )

    kpi_rows = [
        ("total_orders", total_orders),
        ("valid_revenue_orders", valid_revenue_orders),
        ("conversion_rate", round(conversion_rate, 6)),
        ("total_expected_revenue", round(total_expected_revenue, 2)),
        ("total_cash_collected", round(total_cash_collected, 2)),
        ("total_refunds", round(total_refunds, 2)),
        ("net_collected_revenue", round(net_collected_revenue, 2)),
        ("avg_order_value", round(avg_order_value, 2)),
        ("partial_payment_orders", partial_payment_orders),
        ("overpaid_orders", overpaid_orders),
        ("cancelled_orders_with_payment", cancelled_orders_with_payment),
        ("active_cards", active_cards),
        ("points_earned", points_earned),
        ("points_redeemed", points_redeemed),
        ("points_liability", points_liability),
        ("orders_paid_with_points", orders_paid_with_points),
        ("loyalty_revenue_share", round(loyalty_revenue_share, 6)),
    ]

    kpi_summary = pd.DataFrame(kpi_rows, columns=["kpi_name", "kpi_value"])
    kpi_summary.to_csv(analytics_dir / "kpi_summary.csv", index=False)
    return kpi_summary
