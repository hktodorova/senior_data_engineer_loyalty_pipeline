from pipeline.staging import load_raw_data, build_staging
from pipeline.marts import build_marts
from pipeline.data_quality import run_data_quality_checks
from pipeline.analytics import build_analytics, build_kpis


def main() -> None:
    print("=== Retail Loyalty Pipeline ===")

    print("[1/5] Loading raw data...")
    raw = load_raw_data()

    print("[2/5] Building staging tables...")
    stg = build_staging(raw)
    for name, df in stg.items():
        print(f"      {name}: {len(df)} rows")

    print("[3/5] Building mart tables...")
    marts = build_marts(stg)
    for name, df in marts.items():
        print(f"      {name}: {len(df)} rows")

    print("[4/5] Running data quality checks...")
    dq_report = run_data_quality_checks(stg, marts)
    errors = dq_report[dq_report["severity"] == "error"]
    warnings = dq_report[dq_report["severity"] == "warning"]
    print(f"      {len(dq_report)} checks -- {len(errors)} errors, {len(warnings)} warnings")
    failed = dq_report[dq_report["failed_count"] > 0]
    if not failed.empty:
        print(failed[["check_name", "severity", "failed_count"]].to_string(index=False))

    print("[5/5] Building analytics and KPIs...")
    analytics = build_analytics(marts)
    kpis = build_kpis(marts, analytics)
    print("\n--- KPI Summary ---")
    print(kpis.to_string(index=False))

    print("\n=== Pipeline complete. All outputs written to data/ ===")


if __name__ == "__main__":
    main()
