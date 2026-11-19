
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json


@dataclass
class RegistrationResult:
    event_id: int
    registration_status: str
    http_status: int | None = None
    response_event_player_id: int | None = None
    response_uid: str | None = None
    verified_by_detail: bool | None = None
    note: str | None = None
    registered_at_utc: str | None = None

    def to_dict(self):
        return asdict(self)


class RegistrationEngine:
    """
    Submits one explicit event registration at a time
    via the logged-in browser session.
    """

    def __init__(self, page, endpoint, current_uid, timeout_ms=15000):
        self.page = page
        self.endpoint = endpoint
        self.uid = str(current_uid)
        self.timeout_ms = timeout_ms

    async def register(self, event_id):
        stamp = datetime.now(timezone.utc).isoformat()

        print("\n" + "=" * 60)
        print(f"[REGISTRATION] Event ID: {event_id}")
        print(f"[REGISTRATION] Endpoint: {self.endpoint}")
        print("=" * 60)

        try:
            result = await self.page.evaluate(
                """async ({endpoint, eventId, timeoutMs}) => {
                    const controller = new AbortController();
                    const timer = setTimeout(
                        () => controller.abort(),
                        timeoutMs
                    );

                    try {
                        const response = await fetch(endpoint, {
                            method: 'POST',
                            credentials: 'include',
                            headers: {
                                'Accept': 'application/json',
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({ eventId }),
                            signal: controller.signal
                        });

                        const text = await response.text();

                        let body = null;

                        try {
                            body = text ? JSON.parse(text) : null;
                        } catch (_) {
                            body = {
                                rawText: text
                            };
                        }

                        return {
                            status: response.status,
                            statusText: response.statusText,
                            ok: response.ok,
                            responseUrl: response.url,
                            contentType: response.headers.get(
                                'content-type'
                            ),
                            rawBody: text,
                            body: body
                        };

                    } finally {
                        clearTimeout(timer);
                    }
                }""",
                {
                    "endpoint": self.endpoint,
                    "eventId": int(event_id),
                    "timeoutMs": self.timeout_ms
                }
            )

        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"

            print("[REGISTRATION REQUEST ERROR]")
            print(error_message)
            print("=" * 60)

            return RegistrationResult(
                event_id=event_id,
                registration_status="REQUEST_ERROR",
                note=error_message,
                registered_at_utc=stamp
            )

        # --------------------------------------------------
        # 1. EXTRACT HTTP RESPONSE
        # --------------------------------------------------
        http_status = result.get("status")
        body = result.get("body")
        raw_body = result.get("rawBody")

        # --------------------------------------------------
        # 2. PRINT DEBUG INFORMATION
        # --------------------------------------------------
        print("\n[REGISTRATION RESPONSE]")
        print(f"Event ID: {event_id}")
        print(f"HTTP Status: {http_status}")
        print(f"Status Text: {result.get('statusText')}")
        print(f"Response OK: {result.get('ok')}")
        print(f"Response URL: {result.get('responseUrl')}")
        print(f"Content-Type: {result.get('contentType')}")

        print("\n[RAW RESPONSE BODY]")
        print(raw_body if raw_body else "(empty response body)")

        print("\n[PARSED RESPONSE BODY]")
        try:
            print(
                json.dumps(
                    body,
                    ensure_ascii=False,
                    indent=2
                )
            )
        except (TypeError, ValueError):
            print(str(body))

        print("=" * 60 + "\n")

        # --------------------------------------------------
        # 3. VALIDATE RESPONSE BODY
        # --------------------------------------------------
        if not isinstance(body, dict):
            return RegistrationResult(
                event_id=event_id,
                registration_status="INVALID_RESPONSE",
                http_status=http_status,
                verified_by_detail=False,
                note=f"Unexpected response body: {str(body)[:400]}",
                registered_at_utc=stamp
            )

        player = body.get("eventPlayer")

        # --------------------------------------------------
        # 4. SUCCESS RESPONSE
        # --------------------------------------------------
        if http_status == 200 and isinstance(player, dict):

            response_event_id = player.get("eventId")
            response_uid = str(player.get("uid", ""))
            active = player.get("isActive") is True

            if (
                int(response_event_id or -1) == int(event_id)
                and response_uid == self.uid
                and active
            ):
                return RegistrationResult(
                    event_id=event_id,
                    registration_status="REGISTERED_RESPONSE_OK",
                    http_status=http_status,
                    response_event_player_id=player.get("id"),
                    response_uid=response_uid,
                    verified_by_detail=None,
                    note=(
                        "POST returned an active eventPlayer "
                        "matching event ID and UID"
                    ),
                    registered_at_utc=stamp
                )

            return RegistrationResult(
                event_id=event_id,
                registration_status="RESPONSE_MISMATCH",
                http_status=http_status,
                response_event_player_id=player.get("id"),
                response_uid=response_uid,
                verified_by_detail=False,
                note=(
                    "HTTP 200 but eventPlayer did not match "
                    "expected event ID, UID, and active state"
                ),
                registered_at_utc=stamp
            )

        # --------------------------------------------------
        # 5. ERROR RESPONSE
        # --------------------------------------------------
        message = body.get("message")
        error = body.get("error")

        status = (
            "HTTP_ERROR"
            if http_status and http_status != 200
            else "INVALID_RESPONSE"
        )

        # Preserve the full response in the note for diagnosis.
        response_summary = json.dumps(
            body,
            ensure_ascii=False
        )

        note = (
            f"API response: {message or error or response_summary}"
        )

        return RegistrationResult(
            event_id=event_id,
            registration_status=status,
            http_status=http_status,
            response_event_player_id=None,
            response_uid=None,
            verified_by_detail=False,
            note=note[:2000],
            registered_at_utc=stamp
        )
