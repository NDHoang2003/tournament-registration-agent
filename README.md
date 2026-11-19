# Tournament Registration Agent — V2

V2 retains the read-only scanner and adds an explicitly confirmed registration engine.

## Install (macOS)

```bash
cd tournament-registration-agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

Configure `.env`:
- `CURRENT_UID`: your website account UID.
- `EVENT_DETAIL_ENDPOINT_TEMPLATE`: exact GET detail endpoint, with `{event_id}` placeholder.
- `REGISTRATION_ENDPOINT=/api/app/event/register` (POST, observed in DevTools).
- `REGISTRATION_DELAY_SECONDS=3`: pause between registration attempts.

Do not put cookies, authorization headers, or tokens in `.env`. The app uses the
authenticated browser session and same-origin `fetch` with `credentials: include`.

## Run

Scan only (default; no registrations are submitted):

```bash
python main.py --start 7335 --end 8406
```

Registration requires two explicit flags and always performs a fresh scan first:

```bash
python main.py --start 7335 --end 8406 --register --confirm
```

The registration engine only considers events that scan as `OPEN` and where
`current_uid_registered` is explicitly `False`. It re-checks each event immediately
before POST, submits one event at a time, and verifies a successful POST with GET
detail. Existing/duplicate registrations are skipped by the scanner.

## Registration statuses

- `REGISTERED`: POST response matched event ID + UID + active record, and GET detail confirmed it.
- `VERIFY_PENDING`: POST response looked successful but GET detail did not confirm yet.
- `REGISTERED_RESPONSE_OK`: transient internal result; normally converted to `REGISTERED` or `VERIFY_PENDING`.
- `RESPONSE_MISMATCH`: HTTP 200 but returned player record did not match expected event/UID/active state.
- `HTTP_ERROR`: API returned a non-200 response.
- `REQUEST_ERROR`: network/timeout/browser request error.
- `INVALID_RESPONSE`: response was not the expected JSON shape.

On HTTP 401, 403, or 429, the queue stops. Requests are sequential; no parallel
registration, no retry loop, and no bypass of CAPTCHA or anti-automation controls.

## Output

One workbook is reused: `reports/tournament_scan.xlsx`.
- `Scan Results`: latest scan range.
- `Registration Results`: persistent registration audit from SQLite.

SQLite: `data/tournaments.sqlite3`. Registration attempts are retained in
`registration_results`, keyed by event ID.

## Important

The POST endpoint and body are based on the supplied DevTools evidence:
`POST /api/app/event/register` with `{"eventId": <id>}`.
The successful sample response contained an `eventPlayer` object with matching
`eventId`, current `uid`, and `isActive: true`. The app still verifies using GET detail.
Check the website's rules and only register events you intend to join. Review the
preview scan before authorizing a registration run.
