import os
import time
import smtplib
import requests
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid
from dotenv import load_dotenv
from config import get_db_connection

load_dotenv()

# =====================================================
# 1. EVALUATE ATTENDANCE SHORTAGES (< 75%)
# =====================================================
def get_student_shortages(student_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT student_id, register_number, full_name, email, department_id, semester 
        FROM students 
        WHERE student_id = %s
    """, (student_id,))
    student = cursor.fetchone()

    if not student:
        cursor.close()
        db.close()
        return None, []

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
    """, (student_id, student["department_id"], student["semester"]))
    subjects = cursor.fetchall()

    shortages = []
    for sub in subjects:
        total = int(sub["total_classes"] or 0)
        present = int(sub["present_classes"] or 0)

        if total > 0:
            pct = float((present / total) * 100.0)
            if pct < 75.0:
                needed = max(0, (3 * total) - (4 * present))
                shortages.append({
                    "subject_id": sub["subject_id"],
                    "subject_name": sub["subject_name"],
                    "subject_code": sub["subject_code"],
                    "total_classes": total,
                    "present_classes": present,
                    "absent_classes": total - present,
                    "percentage": round(pct, 2),
                    "needed_classes": needed
                })

    cursor.close()
    db.close()
    return student, shortages


# =====================================================
# 2. GENERATE ADVISORY VIA MISTRAL AI API
# =====================================================
def generate_mistral_advisory(student_name, shortages):
    mistral_api_key = os.getenv("MISTRAL_API_KEY")
    
    details = ""
    for s in shortages:
        details += f"- {s['subject_name']}: {s['percentage']}% ({s['present_classes']}/{s['total_classes']} classes attended). Needs {s['needed_classes']} consecutive class(es) to reach 75%.\n"

    prompt = f"""
You are the Academic Attendance Advisor for the Smart Attendance Portal.
A student named {student_name} has fallen below the mandatory 75% attendance threshold.

Attendance Shortage Breakdown:
{details}

Write a formal, encouraging notification email directly to the student:
1. Greet the student by name.
2. Outline the exact subjects, current percentages, and consecutive classes required to regain eligibility.
3. Emphasize attending upcoming sessions to maintain eligibility.
4. Conclude the email formally. 
   - Sign off strictly as:
     Best regards,
     Office of Academic Advising
     Smart Attendance Portal
   - DO NOT include placeholder text such as "[Your Full Name]", "[Your Contact Information]", or any bracketed text.
5. Keep the email clean and readable (avoid markdown headers like ###).
"""

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
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }

        for attempt in range(1, 4):
            try:
                print(f"[Mistral AI] Contacting API for {student_name} (Attempt {attempt}/3)...")
                time.sleep(3)

                response = requests.post(url, headers=headers, json=payload, timeout=25)

                if response.status_code == 200:
                    ai_text = response.json()["choices"][0]["message"]["content"].strip()
                    print(f"[Mistral AI] SUCCESS: Generated dynamic advisory for {student_name} via API.")
                    return ai_text
                
                elif response.status_code == 429:
                    print(f"[Mistral Notice] 429 Rate limited. Waiting 5 seconds before retrying...")
                    time.sleep(5)
                else:
                    print(f"[Mistral Error] HTTP {response.status_code}: {response.text}")
                    break
            except Exception as e:
                print(f"[Mistral Connection Error]: {str(e)}")
                time.sleep(3)

    print("[AI Notice] API could not be reached after retries. Using local template.")
    fallback = f"Dear {student_name},\n\nYour attendance has fallen below the mandatory 75% requirement:\n\n"
    for s in shortages:
        fallback += f"• {s['subject_name']}: {s['percentage']}% ({s['present_classes']}/{s['total_classes']} classes). You must attend the next {s['needed_classes']} consecutive classes.\n"
    fallback += (
        "\nPlease attend your upcoming classes regularly to maintain examination eligibility.\n\n"
        "Best regards,\n"
        "Office of Academic Advising\n"
        "Smart Attendance Portal"
    )
    return fallback


# =====================================================
# 3. NTFY MOBILE PUSH / SMS NOTIFIER
# =====================================================
def send_ntfy_mobile_alert(student_reg_no, student_name, shortages):
    topic = f"attendance_{str(student_reg_no).strip()}"
    url = f"https://ntfy.sh/{topic}"

    lines = [f"Attendance Shortage Alert for {student_name}:"]
    for s in shortages:
        lines.append(f"• {s['subject_name']}: {s['percentage']}% (Attend next {s['needed_classes']} classes)")

    lines.append("\nPlease attend regular classes to avoid exam restrictions.")
    message_body = "\n".join(lines)

    headers = {
        "Title": "Academic Attendance Warning (< 75%)",
        "Priority": "urgent",
        "Tags": "warning,rotating_light,school"
    }

    try:
        response = requests.post(
            url, 
            data=message_body.encode("utf-8"), 
            headers=headers, 
            timeout=10
        )
        if response.status_code == 200:
            print(f"[ntfy Success] Mobile alert sent to topic: {topic}")
            return True
        else:
            print(f"[ntfy Error] HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"[ntfy Error] Failed to send mobile push: {str(e)}")
        return False


# =====================================================
# 4. SMTP CONNECTION & MESSAGE BUILDER
# =====================================================
def build_mime_message(sender_email, to_email, subject, body):
    msg = MIMEMultipart("alternative")
    msg["From"] = f"Academic Attendance Office <{sender_email}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="gmail.com")
    msg["Reply-To"] = sender_email

    part_text = MIMEText(body, "plain", "utf-8")
    msg.attach(part_text)

    html_content = body.replace("\n", "<br>")
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #2d3748; padding: 20px; }}
            .card {{ max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }}
            .header {{ background-color: #0d6efd; color: #ffffff; padding: 16px 20px; font-size: 18px; font-weight: bold; }}
            .body {{ padding: 20px; background: #ffffff; }}
            .footer {{ background-color: #f7fafc; padding: 12px 20px; font-size: 12px; color: #718096; text-align: center; border-top: 1px solid #edf2f7; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">Smart Attendance Advisory</div>
            <div class="body">{html_content}</div>
            <div class="footer">Automated notification from Smart Attendance Portal.</div>
        </div>
    </body>
    </html>
    """
    part_html = MIMEText(html_body, "html", "utf-8")
    msg.attach(part_html)
    return msg


def get_authenticated_smtp_client():
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not smtp_email or not smtp_password:
        print("[SMTP Config Error] Missing SMTP_EMAIL or SMTP_PASSWORD in .env.")
        return None

    try:
        server = smtplib.SMTP_SSL(smtp_server, 465, timeout=20)
        server.login(smtp_email, smtp_password)
        return server
    except Exception as e_ssl:
        print(f"[SMTP Notice] Port 465 failed ({str(e_ssl)}). Retrying Port 587 (STARTTLS)...")

    try:
        server = smtplib.SMTP(smtp_server, 587, timeout=20)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_email, smtp_password)
        return server
    except Exception as e_tls:
        print(f"[SMTP Error] All SMTP ports unreachable ({str(e_tls)}).")
        return None


def send_smtp_email(to_email, subject, body):
    smtp_email = os.getenv("SMTP_EMAIL")
    server = get_authenticated_smtp_client()
    if not server:
        return False

    try:
        msg = build_mime_message(smtp_email, to_email, subject, body)
        server.sendmail(smtp_email, [to_email], msg.as_string())
        server.quit()
        print(f"[SMTP Success] Email delivered directly to student: {to_email}")
        return True
    except Exception as e:
        print(f"[SMTP Error] Failed to send email: {str(e)}")
        try:
            server.quit()
        except Exception:
            pass
        return False


# =====================================================
# 5. ORCHESTRATE ALERT GENERATION & DATABASE LOG
# =====================================================
def process_student_ai_alert(student_id):
    student, shortages = get_student_shortages(student_id)
    if not student:
        print(f"[AI Alert] Student ID {student_id} not found.")
        return None, False

    if not student.get("email"):
        print(f"[AI Alert] Student {student['full_name']} has no email address configured in database.")
        return None, False

    if not shortages:
        print(f"[AI Alert] Student {student['full_name']} has satisfactory attendance (>= 75%). No alert needed.")
        return None, False

    # Check if student already received an alert today (buffered cursor + LIMIT 1 + fetchall)
    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)
    today_str = date.today().isoformat()
    cursor.execute("""
        SELECT recommendation_id 
        FROM ai_recommendations 
        WHERE student_id = %s AND DATE(created_at) = %s
        LIMIT 1
    """, (student_id, today_str))
    already_notified = cursor.fetchone()
    cursor.fetchall()  # Ensure all results are cleared
    cursor.close()
    db.close()

    if already_notified:
        print(f"[AI Alert] {student['full_name']} already received an alert today. Skipping duplicate dispatch.")
        return None, False

    print(f"[AI Alert] Found {len(shortages)} shortage subject(s) for {student['full_name']}. Calling Mistral AI...")
    ai_advisory = generate_mistral_advisory(student["full_name"], shortages)
    if not ai_advisory:
        return None, False

    print(f"[AI Alert] Dispatching email to student's email: {student['email']}...")
    email_sent = send_smtp_email(
        to_email=student["email"],
        subject="Academic Attendance Advisory: Action Required",
        body=ai_advisory
    )

    reg_no = student.get("register_number") or str(student.get("student_id"))
    ntfy_sent = send_ntfy_mobile_alert(reg_no, student["full_name"], shortages)

    if email_sent or ntfy_sent:
        try:
            db = get_db_connection()
            cursor = db.cursor(buffered=True)
            for s in shortages:
                cursor.execute("""
                    INSERT INTO ai_recommendations 
                    (student_id, subject_id, shortage_percentage, required_classes, recommendation_text)
                    VALUES (%s, %s, %s, %s, %s)
                """, (student_id, s["subject_id"], s["percentage"], s["needed_classes"], ai_advisory))
            db.commit()
            cursor.close()
            db.close()
            print("[DB Log] AI Recommendation logged successfully in MySQL.")
        except Exception as e:
            print(f"[DB Log Error]: {str(e)}")

    return ai_advisory, (email_sent or ntfy_sent)


# =====================================================
# 6. AUTOMATED BATCH DISPATCHER (EMAIL + NTFY MOBILE ALERT)
# =====================================================
def send_alerts_to_all_shortage_students(force=False):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("SELECT student_id, register_number, full_name, email FROM students")
    students = cursor.fetchall()

    today_str = date.today().isoformat()
    pending_students = []

    for s in students:
        student_id = s["student_id"]
        _, shortages = get_student_shortages(student_id)

        if shortages:
            cursor.execute("""
                SELECT recommendation_id 
                FROM ai_recommendations 
                WHERE student_id = %s AND DATE(created_at) = %s
                LIMIT 1
            """, (student_id, today_str))
            
            already_notified_today = cursor.fetchone()
            cursor.fetchall()

            if force or not already_notified_today:
                pending_students.append((s, shortages))
            else:
                print(f"[Daily Dispatch] {s['full_name']} already received today's notification. Skipping.")

    if not pending_students:
        cursor.close()
        db.close()
        return {
            "total_evaluated": len(students),
            "shortage_count": 0,
            "emails_delivered": 0
        }

    smtp_email = os.getenv("SMTP_EMAIL")
    server = get_authenticated_smtp_client()

    if not server:
        print("[SMTP Notice] SMTP unavailable on this network. Proceeding with mobile alerts...")

    total_sent = 0

    for s, shortages in pending_students:
        student_id = s["student_id"]
        print(f"\n[Daily Dispatch] Generating advisory for {s['full_name']} ({s['email']})...")
        advisory = generate_mistral_advisory(s["full_name"], shortages)

        email_delivered = False
        if server and smtp_email and s.get("email"):
            msg = build_mime_message(
                sender_email=smtp_email,
                to_email=s["email"],
                subject="Academic Attendance Advisory: Action Required",
                body=advisory
            )
            try:
                server.sendmail(smtp_email, [s["email"]], msg.as_string())
                print(f"[SMTP Success] Delivered directly to {s['email']}")
                email_delivered = True
                total_sent += 1
            except Exception as e:
                print(f"[SMTP Send Failed for {s['email']}]: {str(e)}")

        reg_no = s.get("register_number") or str(s.get("student_id"))
        ntfy_ok = send_ntfy_mobile_alert(reg_no, s["full_name"], shortages)

        if email_delivered or ntfy_ok:
            for item in shortages:
                cursor.execute("""
                    INSERT INTO ai_recommendations 
                    (student_id, subject_id, shortage_percentage, required_classes, recommendation_text)
                    VALUES (%s, %s, %s, %s, %s)
                """, (student_id, item["subject_id"], item["percentage"], item["needed_classes"], advisory))
            db.commit()
            print(f"[DB Log] Advisory recorded in MySQL for {s['full_name']}.")

    if server:
        try:
            server.quit()
        except Exception:
            pass

    cursor.close()
    db.close()

    return {
        "total_evaluated": len(students),
        "shortage_count": len(pending_students),
        "emails_delivered": total_sent
    }