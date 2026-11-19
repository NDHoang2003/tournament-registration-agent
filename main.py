
import argparse
import asyncio
from pathlib import Path

from config import Settings
from core.browser import BrowserSession
from core.tournament_scanner import TournamentScanner
from core.registration_engine import RegistrationEngine
from database.db_manager import Database
from reports.exporter import export_xlsx


async def run():
    parser = argparse.ArgumentParser(
        description="Scan FCM tournaments; optionally register the current UID."
    )

    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--delay", type=float)
    parser.add_argument("--headless", action="store_true")

    parser.add_argument(
        "--keep-browser-open",
        action="store_true",
        help="Keep browser open after execution"
    )

    parser.add_argument(
        "--register",
        action="store_true",
        help="Register eligible OPEN events after a fresh scan."
    )

    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required together with --register; authorizes submissions."
    )

    args = parser.parse_args()

    # --------------------------------------------------
    # 1. LOAD SETTINGS
    # --------------------------------------------------
    settings = Settings.from_env()

    start = settings.start_id if args.start is None else args.start
    end = settings.end_id if args.end is None else args.end
    delay = (
        settings.request_delay_seconds
        if args.delay is None
        else args.delay
    )

    if start > end:
        raise SystemExit("START_ID must be <= END_ID")

    if not settings.event_detail_endpoint_template:
        raise SystemExit(
            "Set EVENT_DETAIL_ENDPOINT_TEMPLATE in .env; see README."
        )

    if not settings.current_uid:
        raise SystemExit("Set CURRENT_UID in .env.")

    if args.confirm and not args.register:
        raise SystemExit("--confirm requires --register.")

    if args.register and not args.confirm:
        raise SystemExit(
            "Registration is disabled without explicit --confirm. "
            "Review the scan first, then run with --register --confirm."
        )

    # --------------------------------------------------
    # 2. INITIALIZE DATABASE
    # --------------------------------------------------
    db = Database(settings.database_path)
    db.initialize()

    scan_results = []

    # --------------------------------------------------
    # 3. OPEN BROWSER SESSION
    # --------------------------------------------------
    async with BrowserSession(
        settings.browser_profile_dir,
        settings.base_url,
        args.headless
    ) as browser:

        await browser.ensure_login()

        scanner = TournamentScanner(
            browser.page,
            settings.event_detail_endpoint_template,
            settings.current_uid,
            settings.request_timeout_ms
        )

        # --------------------------------------------------
        # 4. SCAN TOURNAMENTS
        # --------------------------------------------------
        total = end - start + 1

        for index, event_id in enumerate(
            range(start, end + 1),
            1
        ):
            result = await scanner.scan(event_id)

            scan_results.append(result)
            db.upsert_scan_result(result)

            print(
                f"[SCAN {index}/{total}] "
                f"{event_id}: {result.status} — "
                f"{result.event_name or '-'}"
            )

            if index < total and delay > 0:
                await asyncio.sleep(delay)

        # --------------------------------------------------
        # 5. REGISTRATION ENGINE
        # --------------------------------------------------
        if args.register:

            eligible = [
                result
                for result in scan_results
                if result.status == "OPEN"
                and result.current_uid_registered is False
            ]

            print(f"\nEligible events: {len(eligible)}")

            engine = RegistrationEngine(
                browser.page,
                settings.registration_endpoint,
                settings.current_uid,
                settings.request_timeout_ms
            )

            for index, scan_result in enumerate(
                eligible,
                1
            ):

                # Re-check immediately before POST
                # to reduce stale-scan risk.
                latest = await scanner.scan(
                    scan_result.event_id
                )

                if (
                    latest.status != "OPEN"
                    or latest.current_uid_registered is not False
                ):
                    print(
                        f"[SKIP {scan_result.event_id}] "
                        f"Fresh check: {latest.status}"
                    )
                    continue

                # Submit registration request.
                result = await engine.register(
                    scan_result.event_id
                )

                # --------------------------------------------------
                # 6. VERIFY REGISTRATION
                # --------------------------------------------------
                if (
                    result.registration_status
                    == "REGISTERED_RESPONSE_OK"
                ):

                    verification = await scanner.scan(
                        scan_result.event_id
                    )

                    if verification.status == "REGISTERED":
                        result.verified_by_detail = True
                        result.registration_status = "REGISTERED"
                        result.note = (
                            "POST response matched; "
                            "GET detail confirms current UID"
                        )

                    else:
                        result.verified_by_detail = False
                        result.registration_status = "VERIFY_PENDING"
                        result.note = (
                            "POST response matched but GET detail "
                            f"returned {verification.status}"
                        )

                # Save registration result.
                db.upsert_registration_result(result)

                print(
                    f"[REGISTER {index}/{len(eligible)}] "
                    f"{result.event_id}: "
                    f"{result.registration_status} "
                    f"(HTTP {result.http_status})"
                )

                # Stop on authentication/rate-limit signals.
                if result.http_status in (401, 403, 429):
                    print(
                        "Stopping registration queue due to "
                        "authentication/rate-limit response."
                    )
                    break

                if settings.registration_delay_seconds > 0:
                    await asyncio.sleep(
                        settings.registration_delay_seconds
                    )

        # --------------------------------------------------
        # 7. KEEP BROWSER OPEN FOR DEBUGGING
        # --------------------------------------------------
        if args.keep_browser_open:
            print("\nBrowser is still open.")
            print("You can now inspect DevTools > Network > Fetch/XHR.")
            print("Find the register request and inspect its Response.")
            input("\nPress Enter in this terminal to close the browser...")

    # --------------------------------------------------
    # 8. EXPORT EXCEL REPORT
    # --------------------------------------------------
    report_path = (
        Path(settings.report_dir)
        / "tournament_scan.xlsx"
    )

    export_xlsx(
        scan_results,
        report_path,
        db.list_registration_results()
    )

    print(f"\nReport updated: {report_path}")

    if args.register:
        print(
            "Registration run finished. "
            "Check the Registration Results sheet."
        )


if __name__ == "__main__":
    asyncio.run(run())
