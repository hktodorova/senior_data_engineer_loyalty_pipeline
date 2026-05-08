from pathlib import Path

import pandas as pd

from pipeline.config import DQ_DIR, RAW_DIR


def run_data_quality_checks(
    stg: dict[str, pd.DataFrame],
    marts: dict[str, pd.DataFrame],
    dq_dir: Path = DQ_DIR,
) -> pd.DataFrame:
    """Run all required data quality checks and return a report DataFrame."""
    dq_dir.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []

    def add(check_name: str, severity: str, failed_count: int, description: str) -> None:
        checks.append({"check_name": check_name, "severity": severity,
                        "failed_count": int(failed_count), "description": description})

    orders = stg["stg_orders_master"]
    order_details = stg["stg_order_details"]
    payments = stg["stg_payments"]
    customer_cards = stg["stg_customer_cards"]
    card_points_ledger = stg["stg_card_points_ledger"]
    fact_orders = marts["fact_orders"]
    fact_order_lines = marts["fact_order_lines"]
    fact_payments = marts["fact_payments"]

    # 1. duplicate_orders – before dedup
    raw_orders = pd.read_csv(RAW_DIR / "orders_master.csv")
    add("duplicate_orders", "warning",
        raw_orders["order_id"].dropna().duplicated(keep=False).sum(),
        "Rows in orders_master with a duplicated order_id (before dedup).")

    # 2. duplicate_payment_ids – before dedup
    raw_payments = pd.read_csv(RAW_DIR / "payments.csv")
    add("duplicate_payment_ids", "warning",
        raw_payments["payment_id"].dropna().duplicated(keep=False).sum(),
        "Rows in payments with a duplicated payment_id (before dedup).")

    # 3. orders_without_customer
    valid_customers = stg["stg_customers"]["customer_id"]
    add("orders_without_customer", "warning",
        (~orders["customer_id"].isin(valid_customers)).sum(),
        "Orders whose customer_id does not exist in the customers table.")

    # 4. order_details_without_order
    valid_orders = orders["order_id"]
    add("order_details_without_order", "error",
        (~order_details["order_id"].isin(valid_orders)).sum(),
        "Order detail lines whose order_id does not exist in orders_master.")

    # 5. order_lines_with_invalid_product
    valid_products = stg["stg_products"]["product_id"]
    add("order_lines_with_invalid_product", "warning",
        (~fact_order_lines["product_id"].isin(valid_products)).sum(),
        "Order lines referencing a product_id not found in the products table.")

    # 6. payments_without_order
    add("payments_without_order", "error",
        (~payments["order_id"].isin(valid_orders)).sum(),
        "Payments whose order_id does not exist in orders_master.")

    # 7. payments_with_invalid_card
    valid_cards = customer_cards["card_id"]
    pmt_with_card = payments[payments["card_id"].fillna("").str.strip().str.upper().ne("")]
    add("payments_with_invalid_card", "warning",
        (~pmt_with_card["card_id"].str.strip().str.upper().isin(valid_cards)).sum(),
        "Payments referencing a card_id not present in customer_cards.")

    # 8. payments_with_card_not_owned_by_customer
    card_owner = customer_cards[["card_id", "customer_id"]].rename(columns={"customer_id": "card_owner_id"})
    order_customer = orders[["order_id", "customer_id"]]
    pmt_check = payments[payments["card_id"].fillna("").str.strip().str.upper().ne("")].copy()
    pmt_check["card_id"] = pmt_check["card_id"].str.strip().str.upper()
    pmt_check = pmt_check.merge(card_owner, on="card_id", how="left")
    pmt_check = pmt_check.merge(order_customer, on="order_id", how="left")
    wrong_owner = pmt_check["card_owner_id"].notna() & (pmt_check["card_owner_id"] != pmt_check["customer_id"])
    add("payments_with_card_not_owned_by_customer", "error", wrong_owner.sum(),
        "Payments where the card registered owner differs from the order customer.")

    # 9. payments_using_inactive_or_blocked_card
    card_status_map = customer_cards.set_index("card_id")["card_status"]
    pmt_valid_card = pmt_check[pmt_check["card_id"].isin(card_status_map.index)].copy()
    pmt_valid_card["_card_status"] = pmt_valid_card["card_id"].map(card_status_map)
    add("payments_using_inactive_or_blocked_card", "warning",
        pmt_valid_card["_card_status"].isin(["inactive", "blocked"]).sum(),
        "Payments made with a card whose status is inactive or blocked.")

    # 10. orders_without_payment
    orders_with_payment = payments["order_id"].unique()
    add("orders_without_payment", "info",
        (~fact_orders["order_id"].isin(orders_with_payment)).sum(),
        "Orders that have no associated payment record.")

    # 11. cancelled_orders_with_successful_payment
    add("cancelled_orders_with_successful_payment", "warning",
        ((fact_orders["order_status"] == "cancelled") & fact_orders["has_successful_payment"]).sum(),
        "Orders marked cancelled that still have at least one successful payment.")

    # 12. paid_orders_without_successful_payment
    add("paid_orders_without_successful_payment", "error",
        ((fact_orders["order_status"] == "paid") & ~fact_orders["has_successful_payment"]).sum(),
        "Orders marked paid but lacking any successful payment event.")

    # 13. orders_with_negative_expected_amount
    add("orders_with_negative_expected_amount", "error",
        (fact_orders["order_expected_amount"] < 0).sum(),
        "Orders whose sum of line_net amounts is negative.")

    # 14. orders_overpaid
    add("orders_overpaid", "info", fact_orders["is_overpaid"].sum(),
        "Orders where net_collected_amount exceeds the order_expected_amount.")

    # 15. points_used_without_card
    pts_pmts = fact_payments[fact_payments["is_points_payment"] & (fact_payments["points_used"] > 0)]
    add("points_used_without_card", "warning",
        pts_pmts["card_id"].fillna("").str.strip().eq("").sum(),
        "Point-redemption payments where no card_id is recorded.")

    # 16. points_ledger_invalid_card
    add("points_ledger_invalid_card", "error",
        (~card_points_ledger["card_id"].isin(valid_cards)).sum(),
        "Points ledger entries referencing a card_id not present in customer_cards.")

    # 17. negative_points_balance
    card_balance = card_points_ledger.groupby("card_id")["points_delta"].sum()
    add("negative_points_balance", "error",
        int((card_balance < 0).sum()),
        "Cards whose cumulative points balance is negative.")

    report = pd.DataFrame(checks)
    report.to_csv(dq_dir / "data_quality_report.csv", index=False)
    return report
