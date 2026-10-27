from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from config import get_db_connection
from werkzeug.security import check_password_hash


faculty = Blueprint("faculty", __name__)


# Faculty Login
@faculty.route("/faculty/login", methods=["GET", "POST"])
def faculty_login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM faculty WHERE username=%s",
            (username,)
        )

        faculty_data = cursor.fetchone()

        cursor.close()
        db.close()


        if faculty_data:

            if check_password_hash(
                faculty_data["password"],
                password
            ):

                session["faculty_logged_in"] = True
                session["faculty_id"] = faculty_data["faculty_id"]
                session["faculty_name"] = faculty_data["faculty_name"]
                session["faculty_username"] = faculty_data["username"]

                flash("Login successful", "success")

                return redirect(
                    url_for("faculty.faculty_dashboard")
                )

            else:
                flash("Invalid Password", "danger")

        else:
            flash("Faculty username not found", "danger")


    return render_template("faculty_login.html")



# Temporary Dashboard Route
@faculty.route("/faculty/dashboard")
def faculty_dashboard():

    if "faculty_logged_in" not in session:
        return redirect(
            url_for("faculty.faculty_login")
        )


    return render_template(
        "faculty_dashboard.html",
        faculty_name=session["faculty_name"]
    )



# Faculty Logout
@faculty.route("/faculty/logout")
def faculty_logout():

    session.clear()

    return redirect(
        url_for("faculty.faculty_login")
    )