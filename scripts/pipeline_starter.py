import pandas as pd
from pathlib import Path

RAW_DIR = Path("data/raw")
STAGING_DIR = Path("data/staging")
MARTS_DIR = Path("data/marts")
ANALYTICS_DIR = Path("data/analytics")
DQ_DIR = Path("data/data_quality")

for path in [STAGING_DIR, MARTS_DIR, ANALYTICS_DIR, DQ_DIR]:
    path.mkdir(parents=True, exist_ok=True)


def load_raw_data():
    return {
        "customers": pd.read_csv(RAW_DIR / "customers.csv"),
        "customer_cards": pd.read_csv(RAW_DIR / "customer_cards.csv"),
        "products": pd.read_csv(RAW_DIR / "products.csv"),
        "orders_master": pd.read_csv(RAW_DIR / "orders_master.csv"),
        "order_details": pd.read_csv(RAW_DIR / "order_details.csv"),
        "payments": pd.read_csv(RAW_DIR / "payments.csv"),
        "points_thresholds": pd.read_csv(RAW_DIR / "points_thresholds.csv"),
        "card_points_ledger": pd.read_csv(RAW_DIR / "card_points_ledger.csv"),
    }


def build_staging(raw):
    # TODO
    pass


def build_marts(stg):
    # TODO
    pass


def run_data_quality_checks(stg, marts):
    # TODO
    pass


def build_kpis(marts):
    # TODO
    pass


def write_outputs(stg, marts, dq_report, kpis):
    # TODO
    pass


def main():
    raw = load_raw_data()
    stg = build_staging(raw)
    marts = build_marts(stg)
    dq_report = run_data_quality_checks(stg, marts)
    kpis = build_kpis(marts)
    write_outputs(stg, marts, dq_report, kpis)


if __name__ == "__main__":
    main()
