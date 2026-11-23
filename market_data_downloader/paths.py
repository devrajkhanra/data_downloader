from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT_ROOT / "data"
JOB_DB_PATH = DATA_ROOT / ".download_jobs.sqlite3"
