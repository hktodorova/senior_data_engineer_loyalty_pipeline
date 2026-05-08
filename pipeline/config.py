from pathlib import Path

# Project root
BASE_DIR = Path(__file__).resolve().parents[2]

# Data directories
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
STAGING_DIR = DATA_DIR / "staging"
MARTS_DIR = DATA_DIR / "marts"
ANALYTICS_DIR = DATA_DIR / "analytics"
DQ_DIR = DATA_DIR / "data_quality"

# Optional docs/scripts dirs
DOCS_DIR = BASE_DIR / "docs"
SCRIPTS_DIR = BASE_DIR / "scripts"