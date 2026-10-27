import io
import pandas as pd
from config import get_db_connection
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

def fetch_report_data(report_type, subject_id, specific_date=None, specific_month=None, start_date=None, end_date=None):
    """
    Retrieves student attendance breakdown filtered by daily, monthly, range, or semester criteria.
    Uses 'attendance_date' matching the MySQL schema.
    """
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT s.subject_name, s.subject_code, d.department_name, s.semester
        FROM subjects s
        JOIN departments d ON s.department_id = d.department_id
        WHERE s.subject_id = %s
    """, (subject_id,))
    subject_info = cursor.fetchone()

    if not subject_info:
        cursor.close()
        db.close()
        return None, []

    date_filter = ""
    params = [subject_id]

    if report_type == "daily" and specific_date:
        date_filter = "AND a.attendance_date = %s"
        params.append(specific_date)
    elif report_type == "monthly" and specific_month:
        date_filter = "AND DATE_FORMAT(a.attendance_date, '%Y-%m') = %s"
        params.append(specific_month)
    elif report_type == "range" and start_date and end_date:
        date_filter = "AND a.attendance_date BETWEEN %s AND %s"
        params.extend([start_date, end_date])

    params.append(subject_id)

    query = f"""
        SELECT 
            st.register_number,
            st.full_name,
            COUNT(a.attendance_id) AS total_classes,
            SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_classes,
            SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_classes
        FROM students st
        JOIN subjects sub ON st.department_id = sub.department_id AND st.semester = sub.semester
        LEFT JOIN attendance a 
            ON st.student_id = a.student_id 
            AND a.subject_id = %s 
            {date_filter}
        WHERE sub.subject_id = %s
        GROUP BY st.student_id, st.register_number, st.full_name
        ORDER BY st.register_number ASC
    """

    cursor.execute(query, tuple(params))
    records = cursor.fetchall()
    cursor.close()
    db.close()

    formatted_rows = []
    for row in records:
        total = int(row["total_classes"] or 0)
        present = int(row["present_classes"] or 0)
        absent = int(row["absent_classes"] or 0)
        pct = round((present / total * 100), 2) if total > 0 else 0.0

        formatted_rows.append({
            "register_number": row["register_number"],
            "full_name": row["full_name"],
            "total_classes": total,
            "present_classes": present,
            "absent_classes": absent,
            "percentage": pct
        })

    return subject_info, formatted_rows


def export_to_excel(subject_info, rows, title_meta):
    output = io.BytesIO()
    df = pd.DataFrame(rows)
    df.rename(columns={
        "register_number": "Register Number",
        "full_name": "Student Name",
        "total_classes": "Total Classes",
        "present_classes": "Present Classes",
        "absent_classes": "Absent Classes",
        "percentage": "Percentage (%)"
    }, inplace=True)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Attendance Report", startrow=4)
        worksheet = writer.sheets["Attendance Report"]
        
        worksheet["A1"] = f"Subject: {subject_info['subject_name']} ({subject_info['subject_code']})"
        worksheet["A2"] = f"Department: {subject_info['department_name']} | Semester: {subject_info['semester']}"
        worksheet["A3"] = f"Report Scope: {title_meta}"

    output.seek(0)
    return output


def export_to_pdf(subject_info, rows, title_meta):
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(letter), leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<b>Smart Attendance Report - {subject_info['subject_name']} ({subject_info['subject_code']})</b>", styles["Title"]))
    story.append(Paragraph(f"<b>Department:</b> {subject_info['department_name']} | <b>Semester:</b> {subject_info['semester']} | <b>Scope:</b> {title_meta}", styles["Normal"]))
    story.append(Spacer(1, 15))

    table_data = [["Reg Number", "Student Name", "Total", "Present", "Absent", "Percentage"]]
    for r in rows:
        table_data.append([
            str(r["register_number"]),
            r["full_name"],
            str(r["total_classes"]),
            str(r["present_classes"]),
            str(r["absent_classes"]),
            f"{r['percentage']}%"
        ])

    pdf_table = Table(table_data, colWidths=[120, 240, 70, 70, 70, 90])
    pdf_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
    ]))

    story.append(pdf_table)
    doc.build(story)
    output.seek(0)
    return output