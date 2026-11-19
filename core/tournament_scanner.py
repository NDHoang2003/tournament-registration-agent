
from dataclasses import dataclass, asdict
from datetime import datetime, timezone


@dataclass
class ScanResult:
    event_id: int
    status: str
    http_status: int | None = None
    event_name: str | None = None
    registration_end_at: str | None = None
    event_start_at: str | None = None
    event_status_code: int | str | None = None
    current_uid_registered: bool | None = None
    note: str | None = None
    scanned_at_utc: str | None = None

    def to_dict(self):
        return asdict(self)


class TournamentScanner:
    """
    Read-only GET scanner.

    Registration eligibility is currently based on:
    - event.status == 4 (empirically observed allowed status)
    - registration deadline has not passed
    - current UID is not already registered
    """

    ALLOWED_EVENT_STATUS = 4

    def __init__(
        self,
        page,
        endpoint_template,
        current_uid,
        timeout_ms=15000
    ):
        self.page = page
        self.template = endpoint_template
        self.uid = str(current_uid)
        self.timeout_ms = timeout_ms

    async def scan(self, event_id):
        stamp = datetime.now(timezone.utc).isoformat()

        # --------------------------------------------------
        # 1. GET EVENT DETAIL
        # --------------------------------------------------
        try:
            path = self.template.format(event_id=event_id)

            result = await self.page.evaluate(
                """async ({path, timeoutMs}) => {
                    const c = new AbortController();
                    const t = setTimeout(
                        () => c.abort(),
                        timeoutMs
                    );

                    try {
                        const r = await fetch(path, {
                            method: 'GET',
                            credentials: 'include',
                            headers: {
                                'Accept': 'application/json'
                            },
                            signal: c.signal
                        });

                        const tx = await r.text();
                        let body = null;

                        try {
                            body = tx ? JSON.parse(tx) : null;
                        } catch (_) {
                            body = {rawText: tx.slice(0, 300)};
                        }

                        return {
                            status: r.status,
                            body
                        };

                    } finally {
                        clearTimeout(t);
                    }
                }""",
                {
                    "path": path,
                    "timeoutMs": self.timeout_ms
                }
            )

        except Exception as e:
            return ScanResult(
                event_id,
                "ERROR",
                note=f"{type(e).__name__}: {e}",
                scanned_at_utc=stamp
            )

        code = result.get("status")
        body = result.get("body") or {}

        if not isinstance(body, dict):
            return ScanResult(
                event_id,
                "NO_DATA",
                code,
                note="Invalid response body",
                scanned_at_utc=stamp
            )

        # --------------------------------------------------
        # 2. HTTP RESPONSE VALIDATION
        # --------------------------------------------------
        if code == 404 or body.get("message") == "EventNotFound":
            return ScanResult(
                event_id,
                "NOT_FOUND",
                code,
                note="EventNotFound",
                scanned_at_utc=stamp
            )

        if code != 200:
            return ScanResult(
                event_id,
                "ERROR",
                code,
                note="Unexpected HTTP status",
                scanned_at_utc=stamp
            )

        event = body.get("event")

        if not isinstance(event, dict) or not event.get("id"):
            return ScanResult(
                event_id,
                "NO_DATA",
                code,
                note="Missing event object",
                scanned_at_utc=stamp
            )

        if int(event["id"]) != int(event_id):
            return ScanResult(
                event_id,
                "ERROR",
                code,
                event_name=event.get("name"),
                note="Response event ID mismatch",
                scanned_at_utc=stamp
            )

        # --------------------------------------------------
        # 3. READ EVENT STATUS
        # --------------------------------------------------
        raw_event_status = event.get("status")

        try:
            event_status = int(raw_event_status)
        except (ValueError, TypeError):
            event_status = None

        # --------------------------------------------------
        # 4. CHECK CURRENT UID REGISTRATION
        # --------------------------------------------------
        active = False
        inactive = False

        for item in body.get("eventPlayerInfos") or []:
            if not isinstance(item, dict):
                continue

            ep = item.get("eventPlayer") or {}

            if not isinstance(ep, dict):
                continue

            if str(ep.get("uid", "")) == self.uid:
                if ep.get("isActive") is True:
                    active = True
                else:
                    inactive = True

        # --------------------------------------------------
        # 5. CLASSIFY REGISTRATION STATUS
        # --------------------------------------------------
        if active:
            status = "REGISTERED"
            note = "Current UID has active eventPlayer record"

        elif inactive:
            status = "INACTIVE_RECORD"
            note = (
                "UID record is inactive; "
                "manual review recommended"
            )

        # Event status must be eligible before checking deadline.
        elif event_status != self.ALLOWED_EVENT_STATUS:
            status = "NOT_ALLOWED_STATUS"
            note = (
                f"Event status {raw_event_status!r} "
                f"is not the observed allowed status "
                f"({self.ALLOWED_EVENT_STATUS})"
            )

        # --------------------------------------------------
        # 6. CHECK REGISTRATION DEADLINE
        # --------------------------------------------------
        else:
            deadline = event.get("registrationEndAt")

            if not deadline:
                status = "UNKNOWN_DEADLINE"
                note = "registrationEndAt missing"

            else:
                try:
                    dt = datetime.fromisoformat(
                        deadline.replace("Z", "+00:00")
                    )

                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)

                    if datetime.now(timezone.utc) <= dt:
                        status = "OPEN"
                        note = (
                            "Allowed event status and registration "
                            "deadline has not passed"
                        )
                    else:
                        status = "CLOSED"
                        note = "Registration deadline has passed"

                except (ValueError, TypeError):
                    status = "UNKNOWN_DEADLINE"
                    note = "Invalid registrationEndAt"

        # --------------------------------------------------
        # 7. RETURN SCAN RESULT
        # --------------------------------------------------
        return ScanResult(
            event_id=event_id,
            status=status,
            http_status=code,
            event_name=event.get("name"),
            registration_end_at=event.get("registrationEndAt"),
            event_start_at=event.get("eventStartAt"),
            event_status_code=raw_event_status,
            current_uid_registered=active,
            note=note,
            scanned_at_utc=stamp
        )
