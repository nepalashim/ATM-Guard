from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc
import io
from backend.database import get_db
from backend.models.db import Alert
from backend.utils.auth import get_current_user

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _generate_pdf(title: str, alerts: list, stats: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.units import mm

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    story  = []

    # Title
    story.append(Paragraph(f"ATM Sentinel — {title}", styles["Title"]))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
    story.append(Spacer(1, 8*mm))

    # Stats summary
    summary_data = [
        ["Total Alerts", "HIGH", "MEDIUM", "LOW", "Unacknowledged"],
        [str(stats.get("total", 0)), str(stats.get("high", 0)),
         str(stats.get("medium", 0)), str(stats.get("low", 0)),
         str(stats.get("unacknowledged", 0))],
    ]
    summary_table = Table(summary_data, colWidths=[38*mm]*5)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (1, 1), (1, 1), colors.HexColor("#fee2e2")),
        ("BACKGROUND", (2, 1), (2, 1), colors.HexColor("#fef3c7")),
        ("BACKGROUND", (3, 1), (3, 1), colors.HexColor("#dbeafe")),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 8*mm))

    # Alert table
    if alerts:
        story.append(Paragraph("Alert Details", styles["Heading2"]))
        level_colours = {"HIGH": "#fee2e2", "MEDIUM": "#fef3c7",
                         "LOW": "#dbeafe", "NONE": "#f1f5f9"}
        headers = ["Time", "Camera", "Level", "AE", "YOLO", "Detection", "Ack"]
        rows    = [headers]
        for a in alerts[:200]:
            det = ""
            if a.top_detection:
                import json
                try:
                    d = json.loads(a.top_detection)
                    det = f"{d.get('class_name','')} ({d.get('conf','')})"
                except Exception:
                    det = a.top_detection[:30]
            rows.append([
                a.timestamp.strftime("%H:%M:%S"),
                a.cam_id,
                a.level,
                a.ae_level,
                a.yolo_level,
                det,
                "Yes" if a.acknowledged else "No",
            ])

        col_w = [22*mm, 18*mm, 18*mm, 14*mm, 14*mm, 50*mm, 14*mm]
        tbl   = Table(rows, colWidths=col_w, repeatRows=1)
        style_cmds = [
            ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 8),
            ("GRID",        (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]
        for i, row in enumerate(rows[1:], 1):
            lvl = row[2]
            bg  = level_colours.get(lvl, "#f1f5f9")
            style_cmds.append(("BACKGROUND", (2, i), (2, i), colors.HexColor(bg)))
        tbl.setStyle(TableStyle(style_cmds))
        story.append(tbl)

    doc.build(story)
    return buf.getvalue()


@router.get("/daily")
def daily_report(
    report_date: date = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    target = report_date or date.today()
    start  = datetime.combine(target, datetime.min.time())
    end    = datetime.combine(target, datetime.max.time())

    alerts = db.execute(
        select(Alert).where(Alert.timestamp.between(start, end)).order_by(desc(Alert.timestamp))
    ).scalars().all()

    stats = {
        "total":          len(alerts),
        "high":           sum(1 for a in alerts if a.level == "HIGH"),
        "medium":         sum(1 for a in alerts if a.level == "MEDIUM"),
        "low":            sum(1 for a in alerts if a.level == "LOW"),
        "unacknowledged": sum(1 for a in alerts if not a.acknowledged),
    }

    pdf   = _generate_pdf(f"Daily Report — {target}", alerts, stats)
    fname = f"atm_sentinel_daily_{target}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


@router.get("/weekly")
def weekly_report(db: Session = Depends(get_db), _=Depends(get_current_user)):
    end   = datetime.utcnow()
    start = end - timedelta(days=7)

    alerts = db.execute(
        select(Alert).where(Alert.timestamp.between(start, end)).order_by(desc(Alert.timestamp))
    ).scalars().all()

    stats = {
        "total":          len(alerts),
        "high":           sum(1 for a in alerts if a.level == "HIGH"),
        "medium":         sum(1 for a in alerts if a.level == "MEDIUM"),
        "low":            sum(1 for a in alerts if a.level == "LOW"),
        "unacknowledged": sum(1 for a in alerts if not a.acknowledged),
    }

    pdf   = _generate_pdf("Weekly Report (Last 7 Days)", alerts, stats)
    fname = f"atm_sentinel_weekly_{date.today()}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )
