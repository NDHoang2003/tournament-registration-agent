import os
from dataclasses import dataclass
from dotenv import load_dotenv
from pathlib import Path

@dataclass(frozen=True)
class Settings:
    base_url: str
    event_detail_endpoint_template: str
    registration_endpoint: str
    current_uid: str
    start_id: int
    end_id: int
    request_delay_seconds: float
    registration_delay_seconds: float
    request_timeout_ms: int
    browser_profile_dir: str
    database_path: str
    report_dir: str

    @classmethod
    def from_env(cls):
        load_dotenv(Path(__file__).resolve().parent / ".env")
        return cls(
            os.getenv("BASE_URL", "https://giaidau.fcmobile.garena.vn").rstrip("/"),
            os.getenv("EVENT_DETAIL_ENDPOINT_TEMPLATE", "").strip(),
            os.getenv("REGISTRATION_ENDPOINT", "/api/app/event/register").strip(),
            os.getenv("CURRENT_UID", "").strip(),
            int(os.getenv("START_ID", "7335")), int(os.getenv("END_ID", "8406")),
            float(os.getenv("REQUEST_DELAY_SECONDS", "2")),
            float(os.getenv("REGISTRATION_DELAY_SECONDS", "3")),
            int(os.getenv("REQUEST_TIMEOUT_MS", "15000")),
            os.getenv("BROWSER_PROFILE_DIR", "browser-profile"),
            os.getenv("DATABASE_PATH", "data/tournaments.sqlite3"),
            os.getenv("REPORT_DIR", "reports"))
