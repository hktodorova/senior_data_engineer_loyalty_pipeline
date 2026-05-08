import logging

from pipeline.logger import setup_logging
from pipeline.staging import load_raw_data, build_staging
from pipeline.marts import build_marts
from pipeline.data_quality import run_data_quality_checks
from pipeline.analytics import build_analytics, build_kpis

logger = logging.getLogger(__name__)

def main() -> None:
    setup_logging()

    logger.info("=== Retail Loyalty Pipeline ===")

    logger.info("[1/5] Loading raw data...")
    raw = load_raw_data()
      
    logger.info("[2/5] Building staging tables...")
    stg = build_staging(raw)
    for name, df in stg.items():
        logger.info("      %s: %s rows", name, len(df))

    logger.info("[3/5] Building mart tables...")
    marts = build_marts(stg)
    for name, df in marts.items():
        logger.info("      %s: %s rows", name, len(df))

    logger.info("[4/5] Running data quality checks...")
    dq_report = run_data_quality_checks(stg, marts)
    errors = dq_report[dq_report["severity"] == "error"]
    warnings = dq_report[dq_report["severity"] == "warning"]
    logger.info(
        "      %s checks -- %s errors, %s warnings",
        len(dq_report),
        len(errors),
        len(warnings),
    )
    failed = dq_report[dq_report["failed_count"] > 0]
    if not failed.empty:
        logger.info(failed[["check_name", "severity", "failed_count"]].to_string(index=False))

    logger.info("[5/5] Building analytics and KPIs...")
    analytics = build_analytics(marts)
    kpis = build_kpis(marts, analytics)
    logger.info("\n--- KPI Summary ---")
    logger.info(kpis.to_string(index=False))

    logger.info("\n=== Pipeline complete. All outputs written to data/ ===")


if __name__ == "__main__":
    main()
