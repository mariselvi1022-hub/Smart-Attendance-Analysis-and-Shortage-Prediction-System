from flask import Blueprint, render_template, session, redirect, url_for, flash

student = Blueprint("student", __name__)


# ============================================
# STUDENT DASHBOARD
# ============================================

@student.route("/student/dashboard")
def dashboard():

    # Check whether the student is logged in
    if "student_logged_in" not in session:

        flash("Please login first.", "warning")
        return redirect(url_for("auth.student_login"))

    return render_template(
        "student_dashboard.html",
        student_name=session.get("student_name")
    )


# ============================================
# STUDENT PROFILE
# ============================================

@student.route("/student/profile")
def profile():

    if "student_logged_in" not in session:

        flash("Please login first.", "warning")
        return redirect(url_for("auth.student_login"))

    return render_template(
        "student_profile.html",
        student_name=session.get("student_name")
    )


# ============================================
# STUDENT ATTENDANCE
# ============================================

@student.route("/student/attendance")
def attendance():

    if "student_logged_in" not in session:

        flash("Please login first.", "warning")
        return redirect(url_for("auth.student_login"))

    return render_template(
        "student_attendance.html",
        student_name=session.get("student_name")
    )


# ============================================
# STUDENT PREDICTION
# ============================================

@student.route("/student/prediction")
def prediction():

    if "student_logged_in" not in session:

        flash("Please login first.", "warning")
        return redirect(url_for("auth.student_login"))

    return render_template(
        "student_prediction.html",
        student_name=session.get("student_name")
    )


# ============================================
# STUDENT AI ASSISTANT
# ============================================

@student.route("/student/ai")
def ai_assistant():

    if "student_logged_in" not in session:

        flash("Please login first.", "warning")
        return redirect(url_for("auth.student_login"))

    return render_template(
        "student_ai.html",
        student_name=session.get("student_name")
    )