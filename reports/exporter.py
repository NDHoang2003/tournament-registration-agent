from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

HEADERS = ["Event ID","Status","Event name","Registration deadline (UTC)",
"Event start (UTC)","Event status code","Current UID registered","HTTP status","Note","Scanned at (UTC)"]

def export_xlsx(results, path: Path, registration_results=None):
    wb=Workbook(); ws=wb.active; ws.title="Scan Results"; ws.append(HEADERS)
    for r in results:
        ws.append([r.event_id,r.status,r.event_name,r.registration_end_at,r.event_start_at,
                   r.event_status_code,r.current_uid_registered,r.http_status,r.note,r.scanned_at_utc])
    for cell in ws[1]:
        cell.font=Font(bold=True,color="FFFFFF"); cell.fill=PatternFill("solid",fgColor="1F4E78")
        cell.alignment=Alignment(horizontal="center",vertical="center")
    for i,w in enumerate([12,20,38,28,28,18,24,14,60,28],1):
        ws.column_dimensions[get_column_letter(i)].width=w
    ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions

    reg = wb.create_sheet("Registration Results")
    reg_headers = ["Event ID", "Registration status", "HTTP status",
                   "Event player ID", "Response UID", "Verified by GET",
                   "Note", "Attempted at (UTC)"]
    reg.append(reg_headers)
    for item in registration_results or []:
        reg.append([
            item.get("event_id"), item.get("registration_status"),
            item.get("http_status"), item.get("response_event_player_id"),
            item.get("response_uid"), item.get("verified_by_detail"),
            item.get("note"), item.get("registered_at_utc")
        ])
    for cell in reg[1]:
        cell.font=Font(bold=True,color="FFFFFF")
        cell.fill=PatternFill("solid",fgColor="548235")
        cell.alignment=Alignment(horizontal="center",vertical="center")
    for i,w in enumerate([12,26,14,18,24,18,70,30],1):
        reg.column_dimensions[get_column_letter(i)].width=w
    reg.freeze_panes="A2"
    reg.auto_filter.ref=reg.dimensions

    path.parent.mkdir(parents=True,exist_ok=True); wb.save(path)
