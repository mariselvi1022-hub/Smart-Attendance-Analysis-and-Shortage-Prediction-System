import os
from flask import Flask, render_template
from flask_apscheduler import APScheduler

# Import your existing blueprints
from routes.auth import auth
from routes.admin import admin
from routes.faculty import faculty
from routes.student import student

# Import the batch automated alert dispatcher
from utils.ai_notifier import send_alerts_to_all_shortage_students

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "smart_attendance_secret_key_2026")

# Register Blueprints
app.register_blueprint(auth)
app.register_blueprint(admin)
app.register_blueprint(faculty)
app.register_blueprint(student)

# =====================================================
# BACKGROUND SCHEDULER SETUP (DAILY CRON JOB)
# =====================================================
class SchedulerConfig:
    SCHEDULER_API_ENABLED = False

app.config.from_object(SchedulerConfig())

scheduler = APScheduler()
scheduler.init_app(app)

# Runs automatically every day at 09:00 AM (Server Time)
@scheduler.task("cron", id="daily_shortage_email_job", hour=9, minute=0)
def daily_shortage_mailer_job():
    """
    Executes automatically every day at 9:00 AM.
    Scans every student in the database:
    - If attendance < 75%: drafts and sends Mistral AI recovery email.
    - If attendance >= 75%: ceases sending emails automatically.
    """
    with app.app_context():
        print("\n[Scheduler] Running daily 9:00 AM shortage check (< 75%)...")
        results = send_alerts_to_all_shortage_students()
        print(f"[Scheduler] Completed: {results['emails_delivered']} email(s) delivered out of {results['shortage_count']} shortage student(s).\n")

scheduler.start()


# =====================================================
# DEFAULT HOME / LANDING ROUTE
# =====================================================
@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    # use_reloader=False prevents duplicate background scheduler threads
    app.run(debug=True, port=5000, use_reloader=False)