import os
import math
import json
import calendar
import requests
from datetime import datetime, date

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_file
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from dotenv import load_dotenv
from utils.ai_notifier import (
    process_student_ai_alert,
    get_student_shortages,
    generate_mistral_advisory
)

from config import get_db_connection

from utils.report_generator import (
    fetch_report_data,
    export_to_excel,
    export_to_pdf
)

load_dotenv()

auth = Blueprint("auth", __name__)


# =====================================================
# STUDENT PROFILE ROUTE (VIEW & UPDATE)
# =====================================================
@auth.route("/student/profile", methods=["GET", "POST"])
def student_profile():
    if "student_logged_in" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("auth.student_login"))

    student_id = session["student_id"]
    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_details":
            email = request.form.get("email", "").strip()
            phone = request.form.get("phone", "").strip()

            cursor.execute("""
                UPDATE students 
                SET email = %s, phone = %s 
                WHERE student_id = %s
            """, (email, phone, student_id))
            db.commit()
            flash("Profile details updated successfully!", "success")

        elif action == "change_password":
            current_password = request.form.get("current_password")
            new_password = request.form.get("new_password")
            confirm_password = request.form.get("confirm_password")

            cursor.execute("SELECT password FROM students WHERE student_id = %s", (student_id,))
            user = cursor.fetchone()

            if not check_password_hash(user["password"], current_password):
                flash("Incorrect current password.", "danger")
            elif new_password != confirm_password:
                flash("New passwords do not match.", "danger")
            elif len(new_password) < 6:
                flash("Password must be at least 6 characters long.", "warning")
            else:
                hashed_pw = generate_password_hash(new_password)
                cursor.execute("UPDATE students SET password = %s WHERE student_id = %s", (hashed_pw, student_id))
                db.commit()
                flash("Password changed successfully!", "success")

    cursor.execute("""
        SELECT s.student_id, s.register_number, s.full_name, s.email, 
               s.phone, s.semester, s.academic_year, s.section, s.username,
               d.department_name
        FROM students s
        LEFT JOIN departments d ON s.department_id = d.department_id
        WHERE s.student_id = %s
    """, (student_id,))
    student = cursor.fetchone()

    cursor.close()
    db.close()

    return render_template("profile.html", student=student, student_name=student["full_name"])


# =====================================================
# STUDENT REGISTRATION ROUTE
# =====================================================
@auth.route("/student/register", methods=["GET", "POST"])
def student_register():
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        register_number = request.form["register_number"].strip()
        email = request.form["email"].strip()
        phone = request.form["phone"].strip()
        department_id = request.form["department_id"]
        semester = request.form["semester"]
        academic_year = request.form["academic_year"].strip()
        section = request.form["section"].strip()
        username = request.form["username"].strip()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.student_register"))

        db = get_db_connection()
        cursor = db.cursor(dictionary=True, buffered=True)

        cursor.execute("""
            SELECT student_id FROM students 
            WHERE username = %s OR register_number = %s OR email = %s
        """, (username, register_number, email))
        
        if cursor.fetchone():
            flash("Username, Register Number, or Email already registered.", "warning")
            cursor.close()
            db.close()
            return redirect(url_for("auth.student_register"))

        hashed_password = generate_password_hash(password)

        cursor.execute("""
            INSERT INTO students 
            (register_number, full_name, email, phone, department_id, semester, academic_year, section, username, password)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            register_number,
            full_name,
            email,
            phone,
            department_id,
            semester,
            academic_year,
            section,
            username,
            hashed_password
        ))

        db.commit()
        cursor.close()
        db.close()

        flash("Registration successful! You can now login.", "success")
        return redirect(url_for("auth.student_login"))

    return render_template("student_register.html")


# =====================================================
# STUDENT LOGIN
# =====================================================
@auth.route("/student/login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db_connection()
        cursor = db.cursor(dictionary=True, buffered=True)

        cursor.execute(
            "SELECT * FROM students WHERE username=%s",
            (username,)
        )
        student = cursor.fetchone()

        cursor.close()
        db.close()

        if student:
            if check_password_hash(student["password"], password):
                session["student_logged_in"] = True
                session["student_id"] = student["student_id"]
                session["student_name"] = student["full_name"]
                session["username"] = student["username"]

                flash(f"Welcome, {student['full_name']}!", "success")
                return redirect(url_for("auth.student_dashboard"))
            else:
                flash("Incorrect password.", "danger")
        else:
            flash("Username does not exist.", "danger")

    return render_template("student_login.html")


# =====================================================
# STUDENT DASHBOARD
# =====================================================
@auth.route("/student/dashboard")
def student_dashboard():
    if "student_logged_in" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("auth.student_login"))

    student_id = session["student_id"]
    student, shortages = get_student_shortages(student_id)

    ai_advisory = None
    if shortages:
        ai_advisory = generate_mistral_advisory(session["student_name"], shortages)

    return render_template(
        "student_dashboard.html",
        student_name=session["student_name"],
        ai_advisory=ai_advisory
    )


# =====================================================
# STUDENT ATTENDANCE SUMMARY
# =====================================================
@auth.route("/student/attendance")
def student_attendance():
    if "student_logged_in" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("auth.student_login"))

    student_id = session["student_id"]
    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT student_id, full_name, department_id, semester 
        FROM students 
        WHERE student_id = %s
    """, (student_id,))
    student = cursor.fetchone()

    if not student:
        cursor.close()
        db.close()
        flash("Student record not found.", "danger")
        return redirect(url_for("auth.student_login"))

    cursor.execute("""
        SELECT 
            s.subject_id,
            s.subject_code,
            s.subject_name,
            COUNT(a.attendance_id) AS total_classes,
            SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_classes,
            SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_classes
        FROM subjects s
        LEFT JOIN attendance a 
            ON s.subject_id = a.subject_id AND a.student_id = %s
        WHERE s.department_id = %s AND s.semester = %s
        GROUP BY s.subject_id, s.subject_code, s.subject_name
        ORDER BY s.subject_name ASC
    """, (student_id, student["department_id"], student["semester"]))
    attendance_data = cursor.fetchall()

    total_classes = 0
    total_present = 0
    total_absent = 0

    for row in attendance_data:
        t = int(row["total_classes"] or 0)
        p = int(row["present_classes"] or 0)
        a = int(row["absent_classes"] or 0)

        row["total_classes"] = t
        row["present_classes"] = p
        row["absent_classes"] = a

        pct = float((p / t) * 100.0) if t > 0 else 100.0
        row["percentage"] = round(pct, 2)

        if t == 0:
            row["status"] = "Safe"
        elif pct >= 75.0:
            row["status"] = "Safe"
        elif pct >= 60.0:
            row["status"] = "Warning"
        else:
            row["status"] = "Critical"

        total_classes += t
        total_present += p
        total_absent += a

    overall_percentage = round((total_present / total_classes) * 100.0, 2) if total_classes > 0 else 100.0

    cursor.close()
    db.close()

    return render_template(
        "student_attendance.html",
        student_name=student["full_name"],
        attendance_data=attendance_data,
        total_classes=total_classes,
        total_present=total_present,
        total_absent=total_absent,
        overall_percentage=overall_percentage
    )


# =====================================================
# STUDENT ATTENDANCE HISTORY
# =====================================================
@auth.route("/student/attendance/history")
def attendance_history():
    if "student_logged_in" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("auth.student_login"))

    student_id = session["student_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT
            a.attendance_id, a.attendance_date, a.status,
            s.subject_name, f.faculty_name
        FROM attendance a
        INNER JOIN subjects s ON a.subject_id = s.subject_id
        LEFT JOIN faculty f ON a.marked_by = f.faculty_id
        WHERE a.student_id = %s
        ORDER BY a.attendance_date DESC, a.attendance_id DESC
    """, (student_id,))

    history = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "attendance_history.html",
        student_name=session["student_name"],
        history=history
    )


# =====================================================
# SUBJECT DETAILS & RECOVERY ANALYSIS
# =====================================================
@auth.route("/student/subject/<int:subject_id>")
def subject_details(subject_id):
    if "student_logged_in" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("auth.student_login"))

    student_id = session["student_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT
            s.subject_id, s.subject_name,
            COUNT(a.attendance_id) AS total_classes,
            SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) AS present_classes,
            SUM(CASE WHEN a.status='Absent' THEN 1 ELSE 0 END) AS absent_classes
        FROM subjects s
        LEFT JOIN attendance a ON s.subject_id = a.subject_id AND a.student_id = %s
        WHERE s.subject_id = %s
        GROUP BY s.subject_id, s.subject_name
    """, (student_id, subject_id))

    subject_stat = cursor.fetchone()

    if not subject_stat or subject_stat["subject_name"] is None:
        cursor.close()
        db.close()
        flash("Subject not found or no records available.", "danger")
        return redirect(url_for("auth.student_attendance"))

    total = subject_stat["total_classes"] or 0
    present = subject_stat["present_classes"] or 0
    absent = subject_stat["absent_classes"] or 0

    percentage = round((present / total) * 100, 2) if total > 0 else 0.0

    if percentage >= 75:
        status = "Safe"
    elif percentage >= 60:
        status = "Warning"
    else:
        status = "Critical"

    required_classes = 0
    can_miss_classes = 0

    if percentage < 75:
        needed = (3 * total) - (4 * present)
        required_classes = max(0, needed)
    else:
        margin = math.floor((4 * present - 3 * total) / 3)
        can_miss_classes = max(0, margin)

    cursor.execute("""
        SELECT
            a.attendance_id, a.attendance_date, a.status, f.faculty_name
        FROM attendance a
        LEFT JOIN faculty f ON a.marked_by = f.faculty_id
        WHERE a.student_id = %s AND a.subject_id = %s
        ORDER BY a.attendance_date DESC, a.attendance_id DESC
    """, (student_id, subject_id))

    logs = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "subject_details.html",
        student_name=session["student_name"],
        subject=subject_stat,
        total=total,
        present=present,
        absent=absent,
        percentage=percentage,
        status=status,
        required_classes=required_classes,
        can_miss_classes=can_miss_classes,
        logs=logs
    )


# =====================================================
# ATTENDANCE CALENDAR
# =====================================================
@auth.route("/student/calendar")
def student_calendar():
    if "student_logged_in" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("auth.student_login"))

    student_id = session["student_id"]

    now = datetime.now()
    year = request.args.get("year", type=int, default=now.year)
    month = request.args.get("month", type=int, default=now.month)

    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1

    prev_month = 12 if month == 1 else month - 1
    prev_year = year - 1 if month == 1 else year

    next_month = 1 if month == 12 else month + 1
    next_year = year + 1 if month == 12 else year

    calendar.setfirstweekday(calendar.SUNDAY)

    month_name = calendar.month_name[month]
    month_days = calendar.monthcalendar(year, month)

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT 
            a.attendance_id, 
            a.attendance_date, 
            a.period_number,
            a.status, 
            s.subject_name
        FROM attendance a
        JOIN subjects s ON a.subject_id = s.subject_id
        WHERE a.student_id = %s
          AND YEAR(a.attendance_date) = %s
          AND MONTH(a.attendance_date) = %s
        ORDER BY a.attendance_date ASC, a.period_number ASC
    """, (student_id, year, month))

    records = cursor.fetchall()
    cursor.close()
    db.close()

    attendance_by_date = {}
    for record in records:
        d_str = record["attendance_date"].strftime("%Y-%m-%d") if hasattr(record["attendance_date"], "strftime") else str(record["attendance_date"])
        if d_str not in attendance_by_date:
            attendance_by_date[d_str] = []
        attendance_by_date[d_str].append(record)

    return render_template(
        "attendance_calendar.html",
        student_name=session["student_name"],
        year=year,
        month=month,
        month_name=month_name,
        month_days=month_days,
        attendance_by_date=attendance_by_date,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month
    )


# =====================================================
# ATTENDANCE PREDICTION
# =====================================================
@auth.route("/student/prediction", methods=["GET", "POST"])
def attendance_prediction():
    if "student_logged_in" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("auth.student_login"))

    student_id = session["student_id"]
    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT student_id, full_name, department_id, semester 
        FROM students 
        WHERE student_id = %s
    """, (student_id,))
    student = cursor.fetchone()

    if not student:
        cursor.close()
        db.close()
        flash("Student profile not found.", "danger")
        return redirect(url_for("auth.student_login"))

    cursor.execute("""
        SELECT 
            s.subject_id,
            s.subject_name,
            s.subject_code,
            COUNT(a.attendance_id) AS total_classes,
            SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_classes
        FROM subjects s
        LEFT JOIN attendance a 
            ON s.subject_id = a.subject_id AND a.student_id = %s
        WHERE s.department_id = %s AND s.semester = %s
        GROUP BY s.subject_id, s.subject_name, s.subject_code
        ORDER BY s.subject_name ASC
    """, (student_id, student["department_id"], student["semester"]))
    
    subject_rows = cursor.fetchall()
    summary = []

    for sub in subject_rows:
        total = int(sub["total_classes"] or 0)
        present = int(sub["present_classes"] or 0)
        pct = float((present / total) * 100.0) if total > 0 else 100.0

        summary.append({
            "subject_id": sub["subject_id"],
            "subject_name": sub["subject_name"],
            "subject_code": sub["subject_code"],
            "total_classes": total,
            "present_classes": present,
            "percentage": round(pct, 2)
        })

    cursor.close()
    db.close()

    return render_template(
        "student_prediction.html",
        student_name=student["full_name"],
        summary=summary
    )


# =====================================================
# ATTENDANCE DECISION ADVISOR
# =====================================================
@auth.route("/student/decision-advisor")
@auth.route("/student/advisor")
def student_advisor():
    if "student_logged_in" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("auth.student_login"))

    student_id = session["student_id"]
    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT student_id, full_name, department_id, semester 
        FROM students 
        WHERE student_id = %s
    """, (student_id,))
    student = cursor.fetchone()

    if not student:
        cursor.close()
        db.close()
        flash("Student profile not found.", "danger")
        return redirect(url_for("auth.student_login"))

    cursor.execute("""
        SELECT subject_id, subject_name, subject_code 
        FROM subjects 
        WHERE department_id = %s AND semester = %s
        ORDER BY subject_name
    """, (student["department_id"], student["semester"]))
    subjects = cursor.fetchall()

    advice_list = []

    for sub in subjects:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_classes,
                SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_classes
            FROM attendance 
            WHERE student_id = %s AND subject_id = %s
        """, (student_id, sub["subject_id"]))
        counts = cursor.fetchone()

        total = int(counts["total_classes"] or 0)
        present = int(counts["present_classes"] or 0)
        absent = total - present

        pct = float((present / total) * 100.0) if total > 0 else 100.0

        needed_classes = max(0, (3 * total) - (4 * present))
        safe_margin = max(0, (4 * present - 3 * total) // 3) if total > 0 else 0

        if total == 0:
            status = "Safe"
            priority = "Low"
        elif pct < 75.0:
            status = "Critical"
            priority = "High"
        elif pct < 80.0:
            status = "Warning"
            priority = "Medium"
        else:
            status = "Safe"
            priority = "Low"

        advice_list.append({
            "subject_id": sub["subject_id"],
            "subject_name": sub["subject_name"],
            "subject_code": sub["subject_code"],
            "total_classes": total,
            "present_classes": present,
            "absent_classes": absent,
            "percentage": round(pct, 2),
            "needed_classes": needed_classes,
            "safe_margin": safe_margin,
            "status": status,
            "priority": priority
        })

    priority_order = {"High": 1, "Medium": 2, "Low": 3}
    advice_list.sort(key=lambda x: priority_order.get(x["priority"], 4))

    cursor.close()
    db.close()

    return render_template(
        "student_advisor.html",
        student_name=student["full_name"],
        advice_list=advice_list
    )


# =====================================================
# MISTRAL AI ASSISTANT MODULE (OPENROUTER FREE API FIX)
# =====================================================
@auth.route("/student/ai-assistant", methods=["GET", "POST"])
def ai_assistant():
    if "student_logged_in" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("auth.student_login"))

    student_id = session["student_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT
            s.subject_name,
            COUNT(a.attendance_id) AS total_classes,
            SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) AS present_classes,
            SUM(CASE WHEN a.status='Absent' THEN 1 ELSE 0 END) AS absent_classes
        FROM subjects s
        JOIN attendance a ON s.subject_id = a.subject_id
        WHERE a.student_id = %s
        GROUP BY s.subject_id, s.subject_name
    """, (student_id,))

    subject_data = cursor.fetchall()

    cursor.execute("""
        SELECT
            COUNT(*) AS total_classes,
            SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) AS total_present,
            SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END) AS total_absent
        FROM attendance
        WHERE student_id=%s
    """, (student_id,))

    overall = cursor.fetchone()

    cursor.close()
    db.close()

    total_classes = overall["total_classes"] or 0
    total_present = overall["total_present"] or 0
    overall_pct = round((total_present / total_classes * 100), 2) if total_classes > 0 else 0.0

    context_summary = f"Student Name: {session['student_name']}\nOverall Attendance: {overall_pct}% ({total_present}/{total_classes})\n\nSubject Details:\n"

    subject_metrics = []
    for sub in subject_data:
        t = sub["total_classes"] or 0
        p = sub["present_classes"] or 0
        pct = round((p / t * 100), 2) if t > 0 else 0.0
        
        # Calculate safe margins and recovery needed
        if pct < 75.0:
            needed = max(0, (3 * t) - (4 * p))
            margin = 0
            status_desc = f"Shortage (<75%). Needs {needed} consecutive classes to reach 75%."
        else:
            needed = 0
            margin = max(0, (4 * p - 3 * t) // 3) if t > 0 else 0
            status_desc = f"Safe (>=75%). Can safely miss up to {margin} class(es) without falling below 75%."

        subject_metrics.append({
            "name": sub["subject_name"],
            "pct": pct,
            "present": p,
            "total": t,
            "needed": needed,
            "margin": margin,
            "status_desc": status_desc
        })
        context_summary += f"- {sub['subject_name']}: {pct}% ({p}/{t}) | {status_desc}\n"

    ai_response = None
    user_query = None

    if request.method == "POST":
        user_query = request.form.get("user_query", "").strip()
        mistral_api_key = os.getenv("MISTRAL_API_KEY")

        if user_query:
            prompt = f"""You are the university Academic Attendance Advisor for the Smart Attendance System.
The student has submitted an inquiry regarding their attendance and future plans.

--- VERIFIED DATABASE ATTENDANCE METRICS ---
{context_summary}

--- STUDENT QUESTION ---
{user_query}

--- INSTRUCTIONS ---
1. Provide a direct, helpful, and polite response answering the student's question specifically.
2. If they are asking about taking leave, state clearly how many classes they can safely miss in each subject based on the "Safe margin" values provided above.
3. If they have attendance shortages, emphasize the consecutive classes they must attend.
4. Do NOT output metadata, moderation labels, or one-word tags (e.g., do not say 'User Safety: safe'). Write a real, friendly advising response to the student."""

            use_fallback = True

            if mistral_api_key and mistral_api_key != "your_mistral_api_key_here":
                url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {mistral_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://127.0.0.1:5000",
                    "X-Title": "Smart Attendance System"
                }
                payload = {
                    "model": "openrouter/free",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a friendly, encouraging academic college attendance advisor. Always give a detailed, supportive explanation based on the attendance data."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.4
                }

                try:
                    response = requests.post(url, headers=headers, json=payload, timeout=20)
                    if response.status_code == 200:
                        data = response.json()
                        raw_content = data["choices"][0]["message"]["content"].strip()
                        
                        # Validate that OpenRouter returned an actual advisory, not a moderation flag
                        if len(raw_content) > 30 and "User Safety:" not in raw_content:
                            ai_response = raw_content
                            use_fallback = False
                        else:
                            print(f"[OpenRouter Notice] Output filtered ('{raw_content}'). Using local fallback.")
                    else:
                        print(f"[OpenRouter Notice] API responded with {response.status_code}. Using local smart fallback.")
                except Exception as e:
                    print(f"[OpenRouter Notice] Connection error ({str(e)}). Using local smart fallback.")

            # Fallback engine in case OpenRouter fails, times out, or returns a filter tag
            if use_fallback:
                shortage_items = [m for m in subject_metrics if m["pct"] < 75.0]
                safe_items = [m for m in subject_metrics if m["pct"] >= 75.0]

                lines = [f"Academic Attendance Guidance for {session['student_name']}:\n"]
                lines.append(f"Current Cumulative Attendance: {overall_pct}% ({total_present}/{total_classes} sessions attended).\n")

                if "leave" in user_query.lower() or "miss" in user_query.lower() or "absent" in user_query.lower():
                    lines.append("Leave Feasibility Analysis:")
                    for s in subject_metrics:
                        if s["pct"] >= 75.0:
                            lines.append(f"• {s['name']}: Currently at {s['pct']}%. You can safely miss up to {s['margin']} class(es) while staying above 75%.")
                        else:
                            lines.append(f"• {s['name']}: Currently in shortage at {s['pct']}%. Taking leave is not recommended; you need to attend the next {s['needed']} consecutive classes.")
                else:
                    if shortage_items:
                        lines.append("Deficient Course(s) Below 75% Threshold:")
                        for s in shortage_items:
                            lines.append(f"• {s['name']}: {s['pct']}% ({s['present']}/{s['total']} classes) — Needs {s['needed']} consecutive classes.")
                        lines.append("\nAssessment & Recommendation:")
                        lines.append("Because your attendance is in the critical shortage zone, taking leave is strongly discouraged. Please prioritize attending all upcoming classes.")
                    else:
                        lines.append("Course Breakdown:")
                        for s in safe_items:
                            lines.append(f"• {s['name']}: {s['pct']}% ({s['present']}/{s['total']} classes) — Safe buffer: {s['margin']} class(es).")
                        lines.append("\nAssessment & Recommendation:")
                        lines.append("Your attendance is comfortably above the 75% threshold in all subjects. You have a safe buffer for planned leaves.")

                ai_response = "\n".join(lines)

    return render_template(
        "student_ai_assistant.html",
        student_name=session["student_name"],
        context_summary=context_summary,
        ai_response=ai_response,
        user_query=user_query
    )
# =====================================================
# FACULTY LOGIN
# =====================================================
@auth.route("/faculty/login", methods=["GET", "POST"])
def faculty_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db_connection()
        cursor = db.cursor(dictionary=True, buffered=True)

        cursor.execute(
            "SELECT * FROM faculty WHERE username=%s",
            (username,)
        )
        faculty = cursor.fetchone()

        cursor.close()
        db.close()

        if faculty:
            if check_password_hash(faculty["password"], password):
                session["faculty_logged_in"] = True
                session["faculty_id"] = faculty["faculty_id"]
                session["faculty_name"] = faculty["faculty_name"]
                session["faculty_username"] = faculty["username"]

                flash(f"Welcome, {faculty['faculty_name']}!", "success")
                return redirect(url_for("auth.faculty_dashboard"))
            else:
                flash("Incorrect password.", "danger")
        else:
            flash("Username does not exist.", "danger")

    return render_template("faculty_login.html")


# =====================================================
# FACULTY DASHBOARD
# =====================================================
@auth.route("/faculty/dashboard")
def faculty_dashboard():
    if "faculty_logged_in" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("auth.faculty_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    faculty_id = session["faculty_id"]

    cursor.execute("""
        SELECT 
            s.subject_id,
            s.subject_code,
            s.subject_name,
            s.semester,
            s.department_id,
            d.department_name
        FROM subjects s
        JOIN departments d ON s.department_id = d.department_id
        WHERE s.faculty_id = %s
        ORDER BY s.subject_name
    """, (faculty_id,))

    assigned_subjects = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "faculty_dashboard.html",
        faculty_name=session["faculty_name"],
        workload_list=assigned_subjects
    )


# =====================================================
# MARK ATTENDANCE (BUFFERED CURSOR FIX APPLIED)
# =====================================================
@auth.route("/faculty/mark-attendance/<int:subject_id>", methods=["GET", "POST"])
def mark_attendance(subject_id):
    if "faculty_logged_in" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("auth.faculty_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT 
            s.subject_id, 
            s.subject_name, 
            s.subject_code, 
            s.semester, 
            s.department_id,
            d.department_name
        FROM subjects s
        JOIN departments d ON s.department_id = d.department_id
        WHERE s.subject_id = %s
    """, (subject_id,))
    subject = cursor.fetchone()

    if not subject:
        cursor.close()
        db.close()
        flash("Assigned subject not found.", "danger")
        return redirect(url_for("auth.faculty_dashboard"))

    cursor.execute("""
        SELECT student_id, register_number, full_name, section
        FROM students
        WHERE department_id = %s AND semester = %s
        ORDER BY register_number ASC
    """, (subject["department_id"], subject["semester"]))
    students = cursor.fetchall()

    if request.method == "POST":
        attendance_date = request.form.get("attendance_date")
        selected_periods = request.form.getlist("period_number")
        period_text = request.form.get("period_text", "").strip()

        if not selected_periods and period_text:
            parts = [p.strip() for p in period_text.split(",") if p.strip().isdigit()]
            selected_periods = [p for p in parts if 1 <= int(p) <= 6]

        if not selected_periods:
            flash("Please select at least one Period (1–6).", "danger")
            cursor.close()
            db.close()
            return redirect(url_for("auth.mark_attendance", subject_id=subject_id))

        alerts_triggered = 0
        records_saved = 0

        for period in selected_periods:
            period_num = int(period)

            for student in students:
                status = request.form.get(f"status_{student['student_id']}")

                if not status:
                    continue

                cursor.execute("""
                    SELECT attendance_id FROM attendance
                    WHERE student_id = %s AND subject_id = %s AND attendance_date = %s AND period_number = %s
                    LIMIT 1
                """, (student["student_id"], subject_id, attendance_date, period_num))

                already_marked = cursor.fetchone()
                cursor.fetchall()

                if already_marked:
                    flash(f"Attendance already marked for {student['full_name']} on {attendance_date} (P{period_num}).", "warning")
                    continue

                cursor.execute("""
                    INSERT INTO attendance
                    (student_id, subject_id, attendance_date, period_number, status, marked_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (student["student_id"], subject_id, attendance_date, period_num, status, session["faculty_id"]))
                records_saved += 1

                if status == "Absent":
                    ai_msg, sent = process_student_ai_alert(student["student_id"])
                    if sent:
                        alerts_triggered += 1

        db.commit()

        if records_saved > 0:
            formatted_periods = ", ".join([f"P{p}" for p in selected_periods])
            flash(f"Attendance saved successfully for {formatted_periods} on {attendance_date}.", "success")

        if alerts_triggered > 0:
            flash(f"{alerts_triggered} student(s) received automated warnings via email and mobile push.", "info")

        cursor.close()
        db.close()
        return redirect(url_for("auth.mark_attendance", subject_id=subject_id))

    cursor.close()
    db.close()

    return render_template(
        "mark_attendance.html",
        workload=subject,
        students=students
    )


# =====================================================
# FORGOT PASSWORD
# =====================================================
@auth.route("/student/forgot-password", methods=["GET", "POST"])
def student_forgot_password():
    if request.method == "POST":
        email_or_reg = request.form.get("identifier", "").strip()

        db = get_db_connection()
        cursor = db.cursor(dictionary=True, buffered=True)

        cursor.execute("""
            SELECT student_id, full_name, email, register_number 
            FROM students 
            WHERE email = %s OR register_number = %s
        """, (email_or_reg, email_or_reg))
        student = cursor.fetchone()

        cursor.close()
        db.close()

        if not student:
            flash("No student account found with that email or register number.", "danger")
            return redirect(url_for("auth.student_forgot_password"))

        session["reset_student_id"] = student["student_id"]
        flash("Account verified! Please set your new password.", "info")
        return redirect(url_for("auth.student_reset_password"))

    return render_template("forgot_password.html")


# =====================================================
# RESET PASSWORD
# =====================================================
@auth.route("/student/reset-password", methods=["GET", "POST"])
def student_reset_password():
    if "reset_student_id" not in session:
        flash("Session expired or invalid request. Please verify your account again.", "warning")
        return redirect(url_for("auth.student_forgot_password"))

    student_id = session["reset_student_id"]

    if request.method == "POST":
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.student_reset_password"))

        if len(new_password) < 6:
            flash("Password must be at least 6 characters long.", "warning")
            return redirect(url_for("auth.student_reset_password"))

        hashed_pw = generate_password_hash(new_password)

        db = get_db_connection()
        cursor = db.cursor(dictionary=True, buffered=True)
        cursor.execute("UPDATE students SET password = %s WHERE student_id = %s", (hashed_pw, student_id))
        db.commit()
        cursor.close()
        db.close()

        session.pop("reset_student_id", None)
        flash("Your password has been reset successfully! You can now log in.", "success")
        return redirect(url_for("auth.student_login"))

    return render_template("reset_password.html")


# =====================================================
# ADMIN LOGIN & DASHBOARD
# =====================================================
@auth.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db_connection()
        cursor = db.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM admin WHERE username = %s", (username,))
        admin = cursor.fetchone()
        cursor.close()
        db.close()

        if admin and (check_password_hash(admin["password"], password) or admin["password"] == password):
            session["admin_logged_in"] = True
            session["admin_username"] = admin["username"]
            flash("Admin login successful!", "success")
            return redirect(url_for("auth.admin_dashboard"))
        else:
            flash("Invalid admin username or password.", "danger")

    return render_template("admin_login.html")


@auth.route("/admin/dashboard")
def admin_dashboard():
    if "admin_logged_in" not in session:
        flash("Please login as Admin first.", "warning")
        return redirect(url_for("auth.admin_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("SELECT COUNT(*) AS count FROM students")
    student_count = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) AS count FROM faculty")
    faculty_count = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) AS count FROM subjects")
    subject_count = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) AS count FROM departments")
    dept_count = cursor.fetchone()["count"]

    cursor.close()
    db.close()

    return render_template(
        "admin_dashboard.html",
        admin_name=session.get("admin_username", "Administrator"),
        student_count=student_count,
        faculty_count=faculty_count,
        subject_count=subject_count,
        dept_count=dept_count
    )


# =====================================================
# ADMIN: STUDENT MANAGEMENT
# =====================================================
@auth.route("/admin/students", methods=["GET", "POST"])
@auth.route("/admin/student-management", methods=["GET", "POST"])
def student_management():
    if "admin_logged_in" not in session:
        flash("Please login as Admin first.", "warning")
        return redirect(url_for("auth.admin_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    if request.method == "POST":
        register_number = request.form.get("register_number", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        department_id = request.form.get("department_id")
        semester = request.form.get("semester")
        section = request.form.get("section", "").strip()
        academic_year = request.form.get("academic_year", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password")

        cursor.execute("""
            SELECT student_id FROM students 
            WHERE username = %s OR register_number = %s
        """, (username, register_number))
        
        if cursor.fetchone():
            flash("Username or Register Number already exists.", "warning")
        else:
            hashed_pw = generate_password_hash(password)
            cursor.execute("""
                INSERT INTO students 
                (register_number, full_name, email, phone, department_id, semester, section, academic_year, username, password)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (register_number, full_name, email, phone, department_id, semester, section, academic_year, username, hashed_pw))
            db.commit()
            flash("New student added successfully!", "success")

    cursor.execute("SELECT department_id, department_name FROM departments ORDER BY department_id ASC")
    departments = cursor.fetchall()

    cursor.execute("""
        SELECT s.student_id, s.register_number, s.full_name, s.semester, s.username,
               COALESCE(d.department_name, 'Not Assigned') AS department_name
        FROM students s
        LEFT JOIN departments d ON s.department_id = d.department_id
        ORDER BY s.student_id DESC
    """)
    students = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("student_management.html", students=students, departments=departments)


# =====================================================
# ADMIN: EDIT STUDENT
# =====================================================
@auth.route("/admin/student/edit/<int:student_id>", methods=["GET", "POST"])
def edit_student(student_id):
    if "admin_logged_in" not in session:
        flash("Please login as Admin first.", "warning")
        return redirect(url_for("auth.admin_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        department_id = request.form.get("department_id")
        semester = request.form.get("semester")
        section = request.form.get("section", "").strip()
        academic_year = request.form.get("academic_year", "").strip()

        cursor.execute("""
            UPDATE students 
            SET full_name = %s, email = %s, phone = %s, department_id = %s, 
                semester = %s, section = %s, academic_year = %s
            WHERE student_id = %s
        """, (full_name, email, phone, department_id, semester, section, academic_year, student_id))
        db.commit()
        cursor.close()
        db.close()

        flash("Student details updated successfully!", "success")
        return redirect(url_for("auth.student_management"))

    cursor.execute("SELECT * FROM students WHERE student_id = %s", (student_id,))
    student = cursor.fetchone()

    cursor.execute("SELECT department_id, department_name FROM departments ORDER BY department_id ASC")
    departments = cursor.fetchall()

    cursor.close()
    db.close()

    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("auth.student_management"))

    return render_template("edit_student.html", student=student, departments=departments)


# =====================================================
# ADMIN: DELETE STUDENT
# =====================================================
@auth.route("/admin/student/delete/<int:student_id>", methods=["GET", "POST"])
def delete_student(student_id):
    if "admin_logged_in" not in session:
        flash("Please login as Admin first.", "warning")
        return redirect(url_for("auth.admin_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    try:
        cursor.execute("DELETE FROM attendance WHERE student_id = %s", (student_id,))
        cursor.execute("DELETE FROM ai_recommendations WHERE student_id = %s", (student_id,))
        cursor.execute("DELETE FROM students WHERE student_id = %s", (student_id,))
        db.commit()
        flash("Student and all related attendance records were deleted successfully.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error deleting student: {str(e)}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect(url_for("auth.student_management"))


# =====================================================
# ADMIN: FACULTY MANAGEMENT
# =====================================================
@auth.route("/admin/faculty", methods=["GET", "POST"])
@auth.route("/admin/faculty-management", methods=["GET", "POST"])
def faculty_management():
    if "admin_logged_in" not in session:
        flash("Please login as Admin first.", "warning")
        return redirect(url_for("auth.admin_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    if request.method == "POST":
        faculty_name = request.form.get("faculty_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        department_id = request.form.get("department_id")
        username = request.form.get("username", "").strip()
        password = request.form.get("password")

        cursor.execute("""
            SELECT faculty_id FROM faculty 
            WHERE username = %s OR email = %s
        """, (username, email))

        if cursor.fetchone():
            flash("Username or Email already exists for another faculty.", "warning")
        else:
            hashed_pw = generate_password_hash(password)
            cursor.execute("""
                INSERT INTO faculty (faculty_name, email, phone, department_id, username, password)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (faculty_name, email, phone, department_id, username, hashed_pw))
            db.commit()
            flash("Faculty member added successfully!", "success")

    cursor.execute("SELECT department_id, department_name FROM departments ORDER BY department_name ASC")
    departments = cursor.fetchall()

    cursor.execute("""
        SELECT f.faculty_id, f.faculty_name, f.email, f.phone, f.username,
               COALESCE(d.department_name, 'Not Assigned') AS department_name
        FROM faculty f
        LEFT JOIN departments d ON f.department_id = d.department_id
        ORDER BY f.faculty_id DESC
    """)
    faculty_list = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("faculty_management.html", faculty_list=faculty_list, departments=departments)


# =====================================================
# ADMIN: EDIT FACULTY
# =====================================================
@auth.route("/admin/faculty/edit/<int:faculty_id>", methods=["GET", "POST"])
def edit_faculty(faculty_id):
    if "admin_logged_in" not in session:
        flash("Please login as Admin first.", "warning")
        return redirect(url_for("auth.admin_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    if request.method == "POST":
        faculty_name = request.form.get("faculty_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        department_id = request.form.get("department_id")
        new_password = request.form.get("password", "").strip()

        if new_password:
            hashed_pw = generate_password_hash(new_password)
            cursor.execute("""
                UPDATE faculty 
                SET faculty_name = %s, email = %s, phone = %s, department_id = %s, password = %s
                WHERE faculty_id = %s
            """, (faculty_name, email, phone, department_id, hashed_pw, faculty_id))
        else:
            cursor.execute("""
                UPDATE faculty 
                SET faculty_name = %s, email = %s, phone = %s, department_id = %s
                WHERE faculty_id = %s
            """, (faculty_name, email, phone, department_id, faculty_id))

        db.commit()
        cursor.close()
        db.close()

        flash("Faculty updated successfully!", "success")
        return redirect(url_for("auth.faculty_management"))

    cursor.execute("SELECT * FROM faculty WHERE faculty_id = %s", (faculty_id,))
    faculty = cursor.fetchone()

    cursor.execute("SELECT department_id, department_name FROM departments ORDER BY department_name ASC")
    departments = cursor.fetchall()

    cursor.close()
    db.close()

    if not faculty:
        flash("Faculty member not found.", "danger")
        return redirect(url_for("auth.faculty_management"))

    return render_template("edit_faculty.html", faculty=faculty, departments=departments)


# =====================================================
# ADMIN: DELETE FACULTY
# =====================================================
@auth.route("/admin/faculty/delete/<int:faculty_id>", methods=["GET", "POST"])
def delete_faculty(faculty_id):
    if "admin_logged_in" not in session:
        flash("Please login as Admin first.", "warning")
        return redirect(url_for("auth.admin_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    try:
        cursor.execute("UPDATE subjects SET faculty_id = NULL WHERE faculty_id = %s", (faculty_id,))
        cursor.execute("DELETE FROM faculty_workload WHERE faculty_id = %s", (faculty_id,))
        cursor.execute("UPDATE attendance SET marked_by = NULL WHERE marked_by = %s", (faculty_id,))
        cursor.execute("DELETE FROM faculty WHERE faculty_id = %s", (faculty_id,))
        db.commit()
        flash("Faculty member deleted and subject references unlinked successfully.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error deleting faculty: {str(e)}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect(url_for("auth.faculty_management"))


# =====================================================
# ADMIN: SUBJECT MANAGEMENT
# =====================================================
@auth.route("/admin/subjects", methods=["GET", "POST"])
@auth.route("/admin/subject-management", methods=["GET", "POST"])
def subject_management():
    if "admin_logged_in" not in session:
        flash("Please login as Admin first.", "warning")
        return redirect(url_for("auth.admin_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    if request.method == "POST":
        subject_code = request.form.get("subject_code", "").strip()
        subject_name = request.form.get("subject_name", "").strip()
        semester = request.form.get("semester")
        department_id = request.form.get("department_id")
        faculty_id = request.form.get("faculty_id")

        cursor.execute("SELECT subject_id FROM subjects WHERE subject_code = %s", (subject_code,))
        if cursor.fetchone():
            flash("Subject Code already exists.", "warning")
        else:
            cursor.execute("""
                INSERT INTO subjects (subject_code, subject_name, semester, department_id, faculty_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (subject_code, subject_name, semester, department_id, faculty_id if faculty_id else None))
            db.commit()
            flash("Subject added successfully!", "success")

    cursor.execute("SELECT department_id, department_name FROM departments ORDER BY department_name ASC")
    departments = cursor.fetchall()

    cursor.execute("SELECT faculty_id, faculty_name FROM faculty ORDER BY faculty_name ASC")
    faculty_list = cursor.fetchall()

    cursor.execute("""
        SELECT s.subject_id, s.subject_code, s.subject_name, s.semester,
               COALESCE(d.department_name, 'Not Assigned') AS department_name,
               COALESCE(f.faculty_name, 'Unassigned') AS faculty_name
        FROM subjects s
        LEFT JOIN departments d ON s.department_id = d.department_id
        LEFT JOIN faculty f ON s.faculty_id = f.faculty_id
        ORDER BY s.subject_id DESC
    """)
    subjects = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "subject_management.html",
        subjects=subjects,
        departments=departments,
        faculty_list=faculty_list
    )


# =====================================================
# ADMIN: EDIT SUBJECT
# =====================================================
@auth.route("/admin/subject/edit/<int:subject_id>", methods=["GET", "POST"])
def edit_subject(subject_id):
    if "admin_logged_in" not in session:
        flash("Please login as Admin first.", "warning")
        return redirect(url_for("auth.admin_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    if request.method == "POST":
        subject_code = request.form.get("subject_code", "").strip()
        subject_name = request.form.get("subject_name", "").strip()
        semester = request.form.get("semester")
        department_id = request.form.get("department_id")
        faculty_id = request.form.get("faculty_id")

        cursor.execute("""
            UPDATE subjects 
            SET subject_code = %s, subject_name = %s, semester = %s, department_id = %s, faculty_id = %s
            WHERE subject_id = %s
        """, (subject_code, subject_name, semester, department_id, faculty_id if faculty_id else None, subject_id))
        
        db.commit()
        cursor.close()
        db.close()

        flash("Subject details updated successfully!", "success")
        return redirect(url_for("auth.subject_management"))

    cursor.execute("SELECT * FROM subjects WHERE subject_id = %s", (subject_id,))
    subject = cursor.fetchone()

    cursor.execute("SELECT department_id, department_name FROM departments ORDER BY department_name ASC")
    departments = cursor.fetchall()

    cursor.execute("SELECT faculty_id, faculty_name FROM faculty ORDER BY faculty_name ASC")
    faculty_list = cursor.fetchall()

    cursor.close()
    db.close()

    if not subject:
        flash("Subject not found.", "danger")
        return redirect(url_for("auth.subject_management"))

    return render_template(
        "edit_subject.html",
        subject=subject,
        departments=departments,
        faculty_list=faculty_list
    )


# =====================================================
# ADMIN: DELETE SUBJECT
# =====================================================
@auth.route("/admin/subject/delete/<int:subject_id>", methods=["GET", "POST"])
def delete_subject(subject_id):
    if "admin_logged_in" not in session:
        flash("Please login as Admin first.", "warning")
        return redirect(url_for("auth.admin_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    try:
        cursor.execute("DELETE FROM attendance WHERE subject_id = %s", (subject_id,))
        cursor.execute("DELETE FROM faculty_workload WHERE subject_id = %s", (subject_id,))
        cursor.execute("DELETE FROM ai_recommendations WHERE subject_id = %s", (subject_id,))
        cursor.execute("DELETE FROM subjects WHERE subject_id = %s", (subject_id,))
        db.commit()
        flash("Subject and associated attendance logs deleted successfully.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error deleting subject: {str(e)}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect(url_for("auth.subject_management"))


# =====================================================
# FACULTY: MANAGE SESSIONS
# =====================================================
@auth.route("/faculty/attendance-history/<int:subject_id>")
def manage_subject_attendance(subject_id):
    if "faculty_logged_in" not in session and "admin_logged_in" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("auth.faculty_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT s.subject_id, s.subject_name, s.subject_code, d.department_name, s.semester
        FROM subjects s
        JOIN departments d ON s.department_id = d.department_id
        WHERE s.subject_id = %s
    """, (subject_id,))
    subject = cursor.fetchone()

    cursor.execute("""
        SELECT 
            attendance_date,
            period_number,
            COUNT(attendance_id) AS total_marked,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present_count,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) AS absent_count
        FROM attendance
        WHERE subject_id = %s
        GROUP BY attendance_date, period_number
        ORDER BY attendance_date DESC, period_number ASC
    """, (subject_id,))
    sessions_list = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "manage_attendance_sessions.html",
        subject=subject,
        sessions_list=sessions_list
    )


# =====================================================
# FACULTY: EDIT ATTENDANCE FOR A SPECIFIC SESSION
# =====================================================
@auth.route("/faculty/attendance/edit/<int:subject_id>", methods=["GET", "POST"])
def edit_attendance_session(subject_id):
    if "faculty_logged_in" not in session and "admin_logged_in" not in session:
        flash("Unauthorized access.", "danger")
        return redirect(url_for("auth.faculty_login"))

    attendance_date = request.args.get("date") or request.form.get("attendance_date")
    period_number = request.args.get("period") or request.form.get("period_number")

    if not attendance_date or not period_number:
        flash("Date and Period are required to edit attendance.", "warning")
        return redirect(url_for("auth.manage_subject_attendance", subject_id=subject_id))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT s.subject_id, s.subject_name, s.subject_code, s.semester, s.department_id, d.department_name
        FROM subjects s
        JOIN departments d ON s.department_id = d.department_id
        WHERE s.subject_id = %s
    """, (subject_id,))
    subject = cursor.fetchone()

    if not subject:
        cursor.close()
        db.close()
        flash("Subject not found.", "danger")
        return redirect(url_for("auth.faculty_dashboard"))

    if request.method == "POST":
        cursor.execute("""
            SELECT student_id FROM students
            WHERE department_id = %s AND semester = %s
        """, (subject["department_id"], subject["semester"]))
        students = cursor.fetchall()

        updated_count = 0
        alerts_triggered = 0

        for student in students:
            status = request.form.get(f"status_{student['student_id']}")
            if not status:
                continue

            cursor.execute("""
                SELECT attendance_id, status FROM attendance
                WHERE student_id = %s AND subject_id = %s AND attendance_date = %s AND period_number = %s
                LIMIT 1
            """, (student["student_id"], subject_id, attendance_date, int(period_number)))
            existing = cursor.fetchone()
            cursor.fetchall()

            if existing:
                if existing["status"] != status:
                    cursor.execute("""
                        UPDATE attendance
                        SET status = %s
                        WHERE attendance_id = %s
                    """, (status, existing["attendance_id"]))
                    updated_count += 1
            else:
                faculty_marker = session.get("faculty_id")
                cursor.execute("""
                    INSERT INTO attendance (student_id, subject_id, attendance_date, period_number, status, marked_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (student["student_id"], subject_id, attendance_date, int(period_number), status, faculty_marker))
                updated_count += 1

            if status == "Absent":
                ai_msg, sent = process_student_ai_alert(student["student_id"])
                if sent:
                    alerts_triggered += 1

        db.commit()
        cursor.close()
        db.close()

        flash(f"Attendance for {attendance_date} (Period {period_number}) updated successfully!", "success")
        if alerts_triggered > 0:
            flash(f"{alerts_triggered} student(s) received automated shortage alerts.", "info")

        return redirect(url_for("auth.manage_subject_attendance", subject_id=subject_id))

    cursor.execute("""
        SELECT 
            st.student_id,
            st.register_number,
            st.full_name,
            st.section,
            COALESCE(a.status, 'Present') AS current_status
        FROM students st
        LEFT JOIN attendance a 
            ON st.student_id = a.student_id 
            AND a.subject_id = %s 
            AND a.attendance_date = %s 
            AND a.period_number = %s
        WHERE st.department_id = %s AND st.semester = %s
        ORDER BY st.register_number ASC
    """, (subject_id, attendance_date, int(period_number), subject["department_id"], subject["semester"]))
    student_records = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "edit_attendance_session.html",
        subject=subject,
        attendance_date=attendance_date,
        period_number=int(period_number),
        students=student_records
    )


# =====================================================
# FACULTY/ADMIN: DELETE ATTENDANCE
# =====================================================
@auth.route("/faculty/attendance/delete/<int:subject_id>", methods=["POST", "GET"])
def delete_attendance_by_date(subject_id):
    if "faculty_logged_in" not in session and "admin_logged_in" not in session:
        flash("Unauthorized access.", "danger")
        return redirect(url_for("auth.faculty_login"))

    attendance_date = request.args.get("date") or request.form.get("attendance_date")
    period_number = request.args.get("period") or request.form.get("period_number")

    if not attendance_date:
        flash("Attendance date is required to delete records.", "warning")
        return redirect(url_for("auth.faculty_dashboard"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    try:
        if period_number:
            cursor.execute("""
                DELETE FROM attendance 
                WHERE subject_id = %s AND attendance_date = %s AND period_number = %s
            """, (subject_id, attendance_date, int(period_number)))
            flash(f"Attendance for {attendance_date} (Period {period_number}) deleted successfully.", "success")
        else:
            cursor.execute("""
                DELETE FROM attendance 
                WHERE subject_id = %s AND attendance_date = %s
            """, (subject_id, attendance_date))
            flash(f"All attendance records for {attendance_date} deleted successfully.", "success")

        db.commit()
    except Exception as e:
        db.rollback()
        flash(f"Error deleting attendance: {str(e)}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect(url_for("auth.manage_subject_attendance", subject_id=subject_id))


# =====================================================
# VIEW AI ALERT LOGS
# =====================================================
@auth.route("/ai-alert-logs")
def view_ai_alert_logs():
    if "admin_logged_in" not in session and "faculty_logged_in" not in session:
        flash("Please log in to view alert history.", "warning")
        return redirect(url_for("auth.student_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT 
            r.recommendation_id,
            r.shortage_percentage,
            r.required_classes,
            r.recommendation_text,
            DATE_FORMAT(r.created_at, '%Y-%m-%d %H:%i') AS created_at,
            s.full_name,
            s.email,
            sub.subject_name,
            sub.subject_code
        FROM ai_recommendations r
        JOIN students s ON r.student_id = s.student_id
        JOIN subjects sub ON r.subject_id = sub.subject_id
        ORDER BY r.created_at DESC
    """)
    logs = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template("ai_alert_logs.html", logs=logs)


# =====================================================
# ATTENDANCE REPORTS (ADMIN SEES ALL, FACULTY SEES ASSIGNED)
# =====================================================
@auth.route("/attendance-reports", methods=["GET"])
def attendance_reports():
    if "admin_logged_in" not in session and "faculty_logged_in" not in session:
        flash("Please log in to access reports.", "warning")
        return redirect(url_for("auth.student_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    if "admin_logged_in" in session:
        # Admin can view and generate reports for ALL subjects
        cursor.execute("""
            SELECT subject_id, subject_name, subject_code 
            FROM subjects 
            ORDER BY subject_name ASC
        """)
        subjects = cursor.fetchall()
    else:
        # Faculty sees ONLY their assigned subjects (matching subjects.faculty_id)
        faculty_id = session.get("faculty_id")
        cursor.execute("""
            SELECT DISTINCT s.subject_id, s.subject_name, s.subject_code
            FROM subjects s
            LEFT JOIN faculty_workload fw ON s.subject_id = fw.subject_id
            WHERE s.faculty_id = %s OR fw.faculty_id = %s
            ORDER BY s.subject_name ASC
        """, (faculty_id, faculty_id))
        subjects = cursor.fetchall()

    cursor.close()
    db.close()

    subject_id = request.args.get("subject_id")
    report_type = request.args.get("report_type", "semester")
    specific_date = request.args.get("specific_date")
    specific_month = request.args.get("specific_month")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    report_rows = []
    selected_subject = None

    if subject_id:
        selected_subject, report_rows = fetch_report_data(
            report_type=report_type,
            subject_id=int(subject_id),
            specific_date=specific_date,
            specific_month=specific_month,
            start_date=start_date,
            end_date=end_date
        )

    return render_template(
        "attendance_reports.html",
        subjects=subjects,
        selected_subject_id=int(subject_id) if subject_id else None,
        report_type=report_type,
        specific_date=specific_date,
        specific_month=specific_month,
        start_date=start_date,
        end_date=end_date,
        selected_subject=selected_subject,
        report_rows=report_rows
    )

# =====================================================
# DOWNLOAD ATTENDANCE REPORT (SUPPORTS DATE RANGE)
# =====================================================
@auth.route("/download-attendance-report/<export_format>")
def download_attendance_report(export_format):
    if "admin_logged_in" not in session and "faculty_logged_in" not in session:
        return redirect(url_for("auth.student_login"))

    subject_id = request.args.get("subject_id")
    report_type = request.args.get("report_type", "semester")
    specific_date = request.args.get("specific_date")
    specific_month = request.args.get("specific_month")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    if not subject_id:
        flash("Please select a subject to download.", "warning")
        return redirect(url_for("auth.attendance_reports"))

    subject_info, rows = fetch_report_data(
        report_type=report_type,
        subject_id=int(subject_id),
        specific_date=specific_date,
        specific_month=specific_month,
        start_date=start_date,
        end_date=end_date
    )

    if report_type == "range":
        scope_str = f"Date Range: {start_date} to {end_date}"
    elif report_type == "daily":
        scope_str = f"Date: {specific_date}"
    elif report_type == "monthly":
        scope_str = f"Month: {specific_month}"
    else:
        scope_str = "Full Semester"

    meta_title = f"{report_type.capitalize()} Report ({scope_str})"

    if export_format == "excel":
        file_data = export_to_excel(subject_info, rows, meta_title)
        filename = f"Attendance_{subject_info['subject_code']}_{report_type}.xlsx"
        return send_file(
            file_data,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    elif export_format == "pdf":
        file_data = export_to_pdf(subject_info, rows, meta_title)
        filename = f"Attendance_{subject_info['subject_code']}_{report_type}.pdf"
        return send_file(
            file_data,
            as_attachment=True,
            download_name=filename,
            mimetype="application/pdf"
        )


# =====================================================
# VISUAL ATTENDANCE ANALYTICS HUB
# =====================================================
@auth.route("/admin/analytics")
def admin_analytics():
    if "admin_logged_in" not in session and "faculty_logged_in" not in session:
        flash("Please log in to view analytics.", "warning")
        return redirect(url_for("auth.student_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT DISTINCT 
            d.department_id, 
            d.department_name, 
            s.semester, 
            s.section
        FROM students s
        JOIN departments d ON s.department_id = d.department_id
        ORDER BY d.department_name, s.semester, s.section
    """)
    class_groups = cursor.fetchall()

    selected_dept = request.args.get("dept_id")
    selected_sem = request.args.get("sem")
    selected_sec = request.args.get("sec")

    if not selected_dept and class_groups:
        selected_dept = str(class_groups[0]["department_id"])
        selected_sem = str(class_groups[0]["semester"])
        selected_sec = str(class_groups[0]["section"])

    cursor.execute("""
        SELECT 
            st.student_id,
            st.register_number,
            st.full_name,
            COUNT(a.attendance_id) AS total_marked,
            SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_count
        FROM students st
        LEFT JOIN attendance a ON st.student_id = a.student_id
        WHERE st.department_id = %s AND st.semester = %s AND st.section = %s
        GROUP BY st.student_id, st.register_number, st.full_name
        ORDER BY st.register_number ASC
    """, (selected_dept, selected_sem, selected_sec))
    students_in_class = cursor.fetchall()

    student_names = []
    student_percentages = []
    safe_count = 0
    critical_count = 0

    for s in students_in_class:
        total = int(s["total_marked"] or 0)
        present = int(s["present_count"] or 0)
        pct = round((present / total * 100), 2) if total > 0 else 0.0

        student_names.append(s["full_name"])
        student_percentages.append(pct)

        if pct >= 75.0:
            safe_count += 1
        else:
            critical_count += 1

    cursor.execute("""
        SELECT 
            d.department_name,
            COUNT(a.attendance_id) AS total_sessions,
            SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS total_present
        FROM departments d
        JOIN students st ON d.department_id = st.department_id
        LEFT JOIN attendance a ON st.student_id = a.student_id
        GROUP BY d.department_id, d.department_name
    """)
    dept_stats = cursor.fetchall()

    dept_names = []
    dept_percentages = []
    for d in dept_stats:
        t = int(d["total_sessions"] or 0)
        p = int(d["total_present"] or 0)
        d_pct = round((p / t * 100), 2) if t > 0 else 0.0
        dept_names.append(d["department_name"])
        dept_percentages.append(d_pct)

    cursor.execute("""
        SELECT 
            DATE_FORMAT(a.attendance_date, '%b %Y') as month_label,
            DATE_FORMAT(a.attendance_date, '%Y-%m') as sort_key,
            COUNT(a.attendance_id) as total_month_classes,
            SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_month_classes
        FROM attendance a
        JOIN students st ON a.student_id = st.student_id
        WHERE st.department_id = %s AND st.semester = %s AND st.section = %s
        GROUP BY month_label, sort_key
        ORDER BY sort_key ASC
    """, (selected_dept, selected_sem, selected_sec))
    monthly_stats = cursor.fetchall()

    trend_months = []
    trend_percentages = []
    for m in monthly_stats:
        mt = int(m["total_month_classes"] or 0)
        mp = int(m["present_month_classes"] or 0)
        trend_months.append(m["month_label"])
        trend_percentages.append(round((mp / mt * 100), 2) if mt > 0 else 0.0)

    cursor.close()
    db.close()

    return render_template(
        "analytics.html",
        class_groups=class_groups,
        selected_dept=int(selected_dept) if selected_dept else None,
        selected_sem=int(selected_sem) if selected_sem else None,
        selected_sec=selected_sec,
        student_names=json.dumps(student_names),
        student_percentages=json.dumps(student_percentages),
        safe_count=safe_count,
        critical_count=critical_count,
        dept_names=json.dumps(dept_names),
        dept_percentages=json.dumps(dept_percentages),
        trend_months=json.dumps(trend_months),
        trend_percentages=json.dumps(trend_percentages),
        total_students_in_class=len(students_in_class)
    )


# =====================================================
# LOGOUT
# =====================================================
@auth.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("index"))