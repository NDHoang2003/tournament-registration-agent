import json, sqlite3
from pathlib import Path

class Database:
    def __init__(self, path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
    def connect(self):
        c = sqlite3.connect(self.path); c.row_factory = sqlite3.Row; return c
    def initialize(self):
        with self.connect() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS scan_results(
                event_id INTEGER PRIMARY KEY, status TEXT NOT NULL, http_status INTEGER,
                event_name TEXT, registration_end_at TEXT, event_start_at TEXT,
                event_status_code TEXT, current_uid_registered INTEGER, note TEXT,
                scanned_at_utc TEXT, raw_json TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS registration_results(
                event_id INTEGER PRIMARY KEY, registration_status TEXT NOT NULL,
                http_status INTEGER, response_event_player_id INTEGER, response_uid TEXT,
                verified_by_detail INTEGER, note TEXT, registered_at_utc TEXT)""")
    def upsert_scan_result(self, r):
        d = r.to_dict()
        with self.connect() as c:
            c.execute("""INSERT INTO scan_results VALUES(?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(event_id) DO UPDATE SET status=excluded.status,
            http_status=excluded.http_status,event_name=excluded.event_name,
            registration_end_at=excluded.registration_end_at,event_start_at=excluded.event_start_at,
            event_status_code=excluded.event_status_code,
            current_uid_registered=excluded.current_uid_registered,note=excluded.note,
            scanned_at_utc=excluded.scanned_at_utc,raw_json=excluded.raw_json""",
            (d["event_id"],d["status"],d["http_status"],d["event_name"],
             d["registration_end_at"],d["event_start_at"],str(d["event_status_code"]),
             None if d["current_uid_registered"] is None else int(d["current_uid_registered"]),
             d["note"],d["scanned_at_utc"],json.dumps(d,ensure_ascii=False)))


    def upsert_registration_result(self, result):
        d = result.to_dict()
        with self.connect() as c:
            c.execute("""INSERT INTO registration_results VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(event_id) DO UPDATE SET
            registration_status=excluded.registration_status,
            http_status=excluded.http_status,
            response_event_player_id=excluded.response_event_player_id,
            response_uid=excluded.response_uid,
            verified_by_detail=excluded.verified_by_detail,
            note=excluded.note,
            registered_at_utc=excluded.registered_at_utc""",
            (d["event_id"], d["registration_status"], d["http_status"],
             d["response_event_player_id"], d["response_uid"],
             None if d["verified_by_detail"] is None else int(d["verified_by_detail"]),
             d["note"], d["registered_at_utc"]))

    def list_registration_results(self):
        with self.connect() as c:
            return [dict(row) for row in c.execute(
                "SELECT * FROM registration_results ORDER BY event_id"
            ).fetchall()]
