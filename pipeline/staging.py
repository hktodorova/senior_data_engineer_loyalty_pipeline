from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw")
STAGING_DIR = Path("data/staging")


def load_raw_data(raw_dir: Path = RAW_DIR) -> dict[str, pd.DataFrame]:
    """Load all raw CSV files used by the pipeline."""
    return {
        "card_points_ledger": pd.read_csv(raw_dir / "card_points_ledger.csv"),
        "customer_cards": pd.read_csv(raw_dir / "customer_cards.csv"),
        "customers": pd.read_csv(raw_dir / "customers.csv"),
        "order_details": pd.read_csv(raw_dir / "order_details.csv"),
        "orders_master": pd.read_csv(raw_dir / "orders_master.csv"),
        "payments": pd.read_csv(raw_dir / "payments.csv"),
        "points_thresholds": pd.read_csv(raw_dir / "points_thresholds.csv"),
        "products": pd.read_csv(raw_dir / "products.csv"),
    }


def build_staging(raw: dict[str, pd.DataFrame], staging_dir: Path = STAGING_DIR) -> dict[str, pd.DataFrame]:
    """Build staging tables: type normalization, string normalization, critical-key cleanup and technical deduplication."""
    staging_dir.mkdir(parents=True, exist_ok=True)

    # stg_orders_master
    stg_orders_master = raw["orders_master"].copy()
    stg_orders_master["order_id"] = pd.to_numeric(stg_orders_master["order_id"], errors="coerce")
    stg_orders_master["customer_id"] = pd.to_numeric(stg_orders_master["customer_id"], errors="coerce")
    stg_orders_master["order_date"] = pd.to_datetime(stg_orders_master["order_date"], errors="coerce")
    stg_orders_master["order_status"] = stg_orders_master["order_status"].astype(str).str.strip().str.lower()
    stg_orders_master["sales_channel"] = stg_orders_master["sales_channel"].astype(str).str.strip().str.lower()
    stg_orders_master["currency"] = stg_orders_master["currency"].astype(str).str.strip().str.upper()
    stg_orders_master = stg_orders_master.drop_duplicates(subset="order_id", keep="last")
    stg_orders_master = stg_orders_master.dropna(subset=["order_id", "customer_id"]).copy()

    # stg_order_details
    stg_order_details = raw["order_details"].copy()
    stg_order_details["order_id"] = pd.to_numeric(stg_order_details["order_id"], errors="coerce")
    stg_order_details["line_id"] = pd.to_numeric(stg_order_details["line_id"], errors="coerce")
    stg_order_details["product_id"] = (
        stg_order_details["product_id"].fillna("").astype(str).str.strip().str.upper()
    )
    stg_order_details["quantity"] = pd.to_numeric(stg_order_details["quantity"], errors="coerce").fillna(1)
    stg_order_details["unit_price"] = pd.to_numeric(
        stg_order_details["unit_price"].astype(str).str.replace(" CHF", "", case=False, regex=False),
        errors="coerce",
    )
    stg_order_details["discount_pct"] = pd.to_numeric(
        stg_order_details["discount_pct"], errors="coerce"
    ).fillna(0)
    stg_order_details = stg_order_details.drop_duplicates(
        subset=["order_id", "line_id", "product_id", "quantity", "unit_price", "discount_pct"],
        keep="last",
    )
    stg_order_details = stg_order_details.dropna(subset=["order_id", "line_id"]).copy()

    # stg_payments
    stg_payments = raw["payments"].copy()
    stg_payments["payment_id"] = pd.to_numeric(stg_payments["payment_id"], errors="coerce")
    stg_payments["order_id"] = pd.to_numeric(stg_payments["order_id"], errors="coerce")
    stg_payments["payment_datetime"] = pd.to_datetime(stg_payments["payment_datetime"], errors="coerce")
    stg_payments["payment_type"] = stg_payments["payment_type"].astype(str).str.strip().str.lower()
    stg_payments["payment_status"] = stg_payments["payment_status"].astype(str).str.strip().str.lower()
    stg_payments["payment_amount"] = pd.to_numeric(stg_payments["payment_amount"], errors="coerce").fillna(0)
    stg_payments["points_used"] = pd.to_numeric(stg_payments["points_used"], errors="coerce").fillna(0)
    stg_payments["card_id"] = stg_payments["card_id"].fillna("").astype(str).str.strip().str.upper()
    stg_payments = stg_payments.drop_duplicates(subset="payment_id", keep="last")
    stg_payments = stg_payments.dropna(subset=["payment_id", "order_id"]).copy()

    # stg_customers
    stg_customers = raw["customers"].copy()
    stg_customers["customer_id"] = pd.to_numeric(stg_customers["customer_id"], errors="coerce")
    stg_customers["customer_name"] = stg_customers["customer_name"].astype(str).str.strip()
    stg_customers["segment"] = stg_customers["segment"].astype(str).str.strip().str.upper()
    stg_customers["country"] = stg_customers["country"].astype(str).str.strip().str.title()
    stg_customers["signup_date"] = pd.to_datetime(stg_customers["signup_date"], errors="coerce")
    stg_customers = stg_customers.drop_duplicates(subset="customer_id", keep="last")
    stg_customers = stg_customers.dropna(subset=["customer_id"]).copy()

    # stg_customer_cards
    stg_customer_cards = raw["customer_cards"].copy()
    stg_customer_cards["card_id"] = stg_customer_cards["card_id"].fillna("").astype(str).str.strip().str.upper()
    stg_customer_cards["customer_id"] = pd.to_numeric(stg_customer_cards["customer_id"], errors="coerce")
    stg_customer_cards["card_created_at"] = pd.to_datetime(stg_customer_cards["card_created_at"], errors="coerce")
    stg_customer_cards["card_status"] = stg_customer_cards["card_status"].astype(str).str.strip().str.lower()
    stg_customer_cards = stg_customer_cards.drop_duplicates(subset="card_id", keep="last")
    stg_customer_cards = stg_customer_cards[
        (stg_customer_cards["card_id"] != "") & (stg_customer_cards["customer_id"].notna())
    ].copy()

    # stg_products
    stg_products = raw["products"].copy()
    stg_products["product_id"] = stg_products["product_id"].fillna("").astype(str).str.strip().str.upper()
    stg_products["product_name"] = stg_products["product_name"].astype(str).str.strip()
    stg_products["category"] = stg_products["category"].astype(str).str.strip().str.title()
    stg_products["standard_price"] = pd.to_numeric(stg_products["standard_price"], errors="coerce")
    stg_products = stg_products.drop_duplicates(subset="product_id", keep="last")
    stg_products = stg_products[stg_products["product_id"] != ""].copy()

    # stg_points_thresholds
    stg_points_thresholds = raw["points_thresholds"].copy()
    stg_points_thresholds["threshold_id"] = pd.to_numeric(stg_points_thresholds["threshold_id"], errors="coerce")
    stg_points_thresholds["min_amount"] = pd.to_numeric(stg_points_thresholds["min_amount"], errors="coerce")
    stg_points_thresholds["max_amount"] = pd.to_numeric(stg_points_thresholds["max_amount"], errors="coerce")
    stg_points_thresholds["points_awarded"] = pd.to_numeric(stg_points_thresholds["points_awarded"], errors="coerce")
    stg_points_thresholds = stg_points_thresholds.dropna(
        subset=["threshold_id", "min_amount", "points_awarded"]
    ).copy()

    # stg_card_points_ledger
    stg_card_points_ledger = raw["card_points_ledger"].copy()
    stg_card_points_ledger["order_id"] = pd.to_numeric(stg_card_points_ledger["order_id"], errors="coerce")
    stg_card_points_ledger["card_id"] = (
        stg_card_points_ledger["card_id"].fillna("").astype(str).str.strip().str.upper()
    )
    stg_card_points_ledger = stg_card_points_ledger[stg_card_points_ledger["card_id"] != ""].copy()
    stg_card_points_ledger["event_datetime"] = pd.to_datetime(
        stg_card_points_ledger["event_datetime"], errors="coerce"
    )
    stg_card_points_ledger["event_type"] = stg_card_points_ledger["event_type"].astype(str).str.strip().str.lower()
    stg_card_points_ledger["points_delta"] = pd.to_numeric(
        stg_card_points_ledger["points_delta"], errors="coerce"
    ).fillna(0)

    staging = {
        "stg_orders_master": stg_orders_master,
        "stg_order_details": stg_order_details,
        "stg_payments": stg_payments,
        "stg_customers": stg_customers,
        "stg_customer_cards": stg_customer_cards,
        "stg_products": stg_products,
        "stg_points_thresholds": stg_points_thresholds,
        "stg_card_points_ledger": stg_card_points_ledger,
    }

    for name, df in staging.items():
        df.to_csv(staging_dir / f"{name}.csv", index=False)

    return staging
