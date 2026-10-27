from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)

from werkzeug.security import generate_password_hash

from config import get_db_connection
admin = Blueprint("admin", __name__)

# =====================================================
# STUDENT MANAGEMENT
# =====================================================

@admin.route("/admin/students", methods=["GET", "POST"])
def student_management():

    if "admin_logged_in" not in session:

        flash("Please login first.", "warning")

        return redirect(url_for("admin.admin_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # -----------------------------------
    # ADD STUDENT
    # -----------------------------------

    if request.method == "POST":

        register_number = request.form["register_number"]
        full_name = request.form["full_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        program = request.form["program"]
        department_id = request.form["department_id"]
        semester = request.form["semester"]
        academic_year = request.form["academic_year"]
        section = request.form["section"]
        username = request.form["username"]
        password = request.form["password"]

        # Duplicate Register Number

        cursor.execute(
            "SELECT * FROM students WHERE register_number=%s",
            (register_number,)
        )

        if cursor.fetchone():

            flash("Register Number already exists.", "danger")

            return redirect(url_for("admin.student_management"))

        # Duplicate Email

        cursor.execute(
            "SELECT * FROM students WHERE email=%s",
            (email,)
        )

        if cursor.fetchone():

            flash("Email already exists.", "danger")

            return redirect(url_for("admin.student_management"))

        # Duplicate Username

        cursor.execute(
            "SELECT * FROM students WHERE username=%s",
            (username,)
        )

        if cursor.fetchone():

            flash("Username already exists.", "danger")

            return redirect(url_for("admin.student_management"))

        hashed_password = generate_password_hash(password)

        cursor.execute(
            """
            INSERT INTO students
            (
                register_number,
                full_name,
                email,
                phone,
                program,
                department_id,
                username,
                password,
                semester,
                academic_year,
                section
            )
            VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                register_number,
                full_name,
                email,
                phone,
                program,
                department_id,
                username,
                hashed_password,
                semester,
                academic_year,
                section
            )
        )

        db.commit()

        flash("Student added successfully.", "success")

        return redirect(url_for("admin.student_management"))

    # -----------------------------------
    # LOAD DEPARTMENTS
    # -----------------------------------

    cursor.execute(
        """
        SELECT
            department_id,
            department_name
        FROM departments
        ORDER BY department_name
        """
    )

    departments = cursor.fetchall()

    # -----------------------------------
    # LOAD STUDENTS
    # -----------------------------------

    cursor.execute(
        """
        SELECT
            student_id,
            register_number,
            full_name,
            program,
            semester,
            username
        FROM students
        ORDER BY student_id DESC
        """
    )

    student_list = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "student_management.html",
        departments=departments,
        student_list=student_list
    )
# =====================================================
# EDIT STUDENT
# =====================================================

@admin.route("/admin/students/edit/<int:student_id>", methods=["GET", "POST"])
def edit_student(student_id):

    if "admin_logged_in" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("admin.admin_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Load Departments
    cursor.execute("""
        SELECT department_id, department_name
        FROM departments
        ORDER BY department_name
    """)
    departments = cursor.fetchall()

    # Load Student
    cursor.execute(
        "SELECT * FROM students WHERE student_id=%s",
        (student_id,)
    )

    student = cursor.fetchone()

    if student is None:
        flash("Student not found.", "danger")
        cursor.close()
        db.close()
        return redirect(url_for("admin.student_management"))

    # Update Student
    if request.method == "POST":

        register_number = request.form["register_number"]
        full_name = request.form["full_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        program = request.form["program"]
        department_id = request.form["department_id"]
        semester = request.form["semester"]
        academic_year = request.form["academic_year"]
        section = request.form["section"]
        username = request.form["username"]

        cursor.execute("""
            UPDATE students
            SET
                register_number=%s,
                full_name=%s,
                email=%s,
                phone=%s,
                program=%s,
                department_id=%s,
                semester=%s,
                academic_year=%s,
                section=%s,
                username=%s
            WHERE student_id=%s
        """,
        (
            register_number,
            full_name,
            email,
            phone,
            program,
            department_id,
            semester,
            academic_year,
            section,
            username,
            student_id
        ))

        db.commit()

        cursor.close()
        db.close()

        flash("Student updated successfully.", "success")

        return redirect(url_for("admin.student_management"))

    cursor.close()
    db.close()

    return render_template(
        "edit_student.html",
        student=student,
        departments=departments
    )



# =====================================================
# ADMIN LOGIN
# =====================================================

@admin.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM admin WHERE username=%s",
            (username,)
        )

        admin_user = cursor.fetchone()

        cursor.close()
        db.close()

        if admin_user:

            # Current database stores plain text password
            if admin_user["password"] == password:

                session["admin_logged_in"] = True
                session["admin_id"] = admin_user["admin_id"]
                session["admin_name"] = admin_user["full_name"]

                flash(
                    f"Welcome, {admin_user['full_name']}!",
                    "success"
                )

                return redirect(url_for("admin.admin_dashboard"))

            else:

                flash("Incorrect password.", "danger")

        else:

            flash("Username does not exist.", "danger")

    return render_template("admin_login.html")


# =====================================================
# ADMIN DASHBOARD
# =====================================================

@admin.route("/admin/dashboard")
def admin_dashboard():

    if "admin_logged_in" not in session:

        flash("Please login first.", "warning")

        return redirect(url_for("admin.admin_login"))

    return render_template(
        "admin_dashboard.html",
        admin_name=session["admin_name"]
    )


# =====================================================
# FACULTY MANAGEMENT
# =====================================================

@admin.route("/admin/faculty", methods=["GET", "POST"])
def faculty_management():

    if "admin_logged_in" not in session:

        flash("Please login first.", "warning")

        return redirect(url_for("admin.admin_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # ------------------------------
    # ADD FACULTY
    # ------------------------------

    if request.method == "POST":

        faculty_name = request.form["faculty_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        department_id = request.form["department_id"]
        username = request.form["username"]
        password = request.form["password"]

        cursor.execute(
            "SELECT * FROM faculty WHERE username=%s",
            (username,)
        )

        if cursor.fetchone():

            flash("Username already exists.", "danger")

        else:

            hashed_password = generate_password_hash(password)

            cursor.execute(
                """
                INSERT INTO faculty
                (
                    faculty_name,
                    email,
                    phone,
                    department_id,
                    username,
                    password
                )
                VALUES
                (%s,%s,%s,%s,%s,%s)
                """,
                (
                    faculty_name,
                    email,
                    phone,
                    department_id,
                    username,
                    hashed_password
                )
            )

            db.commit()

            flash("Faculty added successfully.", "success")

            return redirect(url_for("admin.faculty_management"))

    # ------------------------------
    # VIEW FACULTY
    # ------------------------------

    cursor.execute(
        """
        SELECT
            faculty.faculty_id,
            faculty.faculty_name,
            faculty.email,
            faculty.username,
            departments.department_name
        FROM faculty
        LEFT JOIN departments
        ON faculty.department_id = departments.department_id
        ORDER BY faculty.faculty_id DESC
        """
    )

    faculty_list = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "faculty_management.html",
        faculty_list=faculty_list
    )
# =====================================================
# EDIT FACULTY
# =====================================================

@admin.route("/admin/faculty/edit/<int:faculty_id>", methods=["GET", "POST"])
def edit_faculty(faculty_id):

    if "admin_logged_in" not in session:

        flash("Please login first.", "warning")

        return redirect(url_for("admin.admin_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Get faculty details
    cursor.execute(
        "SELECT * FROM faculty WHERE faculty_id=%s",
        (faculty_id,)
    )

    faculty = cursor.fetchone()

    if faculty is None:

        flash("Faculty not found.", "danger")

        cursor.close()
        db.close()

        return redirect(url_for("admin.faculty_management"))

    # Update faculty
    if request.method == "POST":

        faculty_name = request.form["faculty_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        department_id = request.form["department_id"]
        username = request.form["username"]

        cursor.execute(
            """
            UPDATE faculty
            SET
                faculty_name=%s,
                email=%s,
                phone=%s,
                department_id=%s,
                username=%s
            WHERE faculty_id=%s
            """,
            (
                faculty_name,
                email,
                phone,
                department_id,
                username,
                faculty_id
            )
        )

        db.commit()

        cursor.close()
        db.close()

        flash("Faculty updated successfully.", "success")

        return redirect(url_for("admin.faculty_management"))

    cursor.close()
    db.close()

    return render_template(
        "edit_faculty.html",
        faculty=faculty
    )
# =====================================================
# DELETE FACULTY
# =====================================================

@admin.route("/admin/faculty/delete/<int:faculty_id>")
def delete_faculty(faculty_id):

    if "admin_logged_in" not in session:

        flash("Please login first.", "warning")

        return redirect(url_for("admin.admin_login"))

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        "DELETE FROM faculty WHERE faculty_id=%s",
        (faculty_id,)
    )

    db.commit()

    cursor.close()
    db.close()

    flash("Faculty deleted successfully.", "success")

    return redirect(url_for("admin.faculty_management"))
# =====================================================
# SUBJECT MANAGEMENT
# =====================================================

@admin.route("/admin/subjects", methods=["GET", "POST"])
def subject_management():

    if "admin_logged_in" not in session:

        flash("Please login first.", "warning")

        return redirect(url_for("admin.admin_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # -----------------------------------
    # ADD SUBJECT
    # -----------------------------------

    if request.method == "POST":

        subject_code = request.form["subject_code"]
        subject_name = request.form["subject_name"]
        semester = request.form["semester"]
        department_id = request.form["department_id"]
        faculty_id = request.form["faculty_id"]

        # Check duplicate subject code

        cursor.execute(
            "SELECT * FROM subjects WHERE subject_code=%s",
            (subject_code,)
        )

        if cursor.fetchone():

            flash("Subject Code already exists.", "danger")

        else:

            cursor.execute(
                """
                INSERT INTO subjects
                (
                    subject_code,
                    subject_name,
                    semester,
                    department_id,
                    faculty_id
                )
                VALUES
                (%s,%s,%s,%s,%s)
                """,
                (
                    subject_code,
                    subject_name,
                    semester,
                    department_id,
                    faculty_id
                )
            )

            db.commit()

            flash("Subject added successfully.", "success")

            return redirect(url_for("admin.subject_management"))

    # -----------------------------------
    # LOAD FACULTY
    # -----------------------------------

    cursor.execute(
        """
        SELECT
            faculty_id,
            faculty_name
        FROM faculty
        ORDER BY faculty_name
        """
    )

    faculty_list = cursor.fetchall()

    # -----------------------------------
    # LOAD SUBJECTS
    # -----------------------------------

    cursor.execute(
        """
        SELECT

            subjects.subject_id,
            subjects.subject_code,
            subjects.subject_name,
            subjects.semester,

            departments.department_name,

            faculty.faculty_name

        FROM subjects

        LEFT JOIN departments
        ON subjects.department_id = departments.department_id

        LEFT JOIN faculty
        ON subjects.faculty_id = faculty.faculty_id

        ORDER BY subjects.subject_id DESC
        """
    )

    subject_list = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "subject_management.html",
        faculty_list=faculty_list,
        subject_list=subject_list
    )

# =====================================================
# EDIT SUBJECT
# =====================================================

@admin.route("/admin/subjects/edit/<int:subject_id>", methods=["GET", "POST"])
def edit_subject(subject_id):

    if "admin_logged_in" not in session:

        flash("Please login first.", "warning")

        return redirect(url_for("admin.admin_login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # -----------------------------------
    # UPDATE SUBJECT
    # -----------------------------------

    if request.method == "POST":

        subject_code = request.form["subject_code"]
        subject_name = request.form["subject_name"]
        semester = request.form["semester"]
        department_id = request.form["department_id"]
        faculty_id = request.form["faculty_id"]

        cursor.execute(
            """
            UPDATE subjects
            SET
                subject_code=%s,
                subject_name=%s,
                semester=%s,
                department_id=%s,
                faculty_id=%s
            WHERE subject_id=%s
            """,
            (
                subject_code,
                subject_name,
                semester,
                department_id,
                faculty_id,
                subject_id
            )
        )

        db.commit()

        flash("Subject updated successfully.", "success")

        cursor.close()
        db.close()

        return redirect(url_for("admin.subject_management"))

    # -----------------------------------
    # LOAD SUBJECT
    # -----------------------------------

    cursor.execute(
        "SELECT * FROM subjects WHERE subject_id=%s",
        (subject_id,)
    )

    subject = cursor.fetchone()

    # -----------------------------------
    # LOAD DEPARTMENTS
    # -----------------------------------

    cursor.execute(
        """
        SELECT
            department_id,
            department_name
        FROM departments
        ORDER BY department_name
        """
    )

    departments = cursor.fetchall()

    # -----------------------------------
    # LOAD FACULTY
    # -----------------------------------

    cursor.execute(
        """
        SELECT
            faculty_id,
            faculty_name
        FROM faculty
        ORDER BY faculty_name
        """
    )

    faculty_list = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "edit_subject.html",
        subject=subject,
        departments=departments,
        faculty_list=faculty_list
    )
# =====================================================
# DELETE SUBJECT
# =====================================================

@admin.route("/admin/subjects/delete/<int:subject_id>")
def delete_subject(subject_id):

    if "admin_logged_in" not in session:

        flash("Please login first.", "warning")

        return redirect(url_for("admin.admin_login"))

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        "DELETE FROM subjects WHERE subject_id=%s",
        (subject_id,)
    )

    db.commit()

    cursor.close()
    db.close()

    flash("Subject deleted successfully.", "success")

    return redirect(url_for("admin.subject_management"))
# =====================================================
# FACULTY WORKLOAD MANAGEMENT
# =====================================================

@admin.route("/faculty-workload", methods=["GET", "POST"])
def faculty_workload():

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        faculty_id = request.form["faculty_id"]
        department_id = request.form["department_id"]
        subject_id = request.form["subject_id"]
        semester = request.form["semester"]
        section = request.form["section"]

        # Check duplicate assignment
        cursor.execute("""
            SELECT *
            FROM faculty_workload
            WHERE faculty_id=%s
            AND subject_id=%s
            AND semester=%s
            AND section=%s
        """,
        (
            faculty_id,
            subject_id,
            semester,
            section
        ))

        if cursor.fetchone():

            flash(
                "This workload is already assigned.",
                "warning"
            )

        else:

            cursor.execute("""
                INSERT INTO faculty_workload
                (
                    faculty_id,
                    department_id,
                    subject_id,
                    semester,
                    section
                )
                VALUES
                (%s,%s,%s,%s,%s)
            """,
            (
                faculty_id,
                department_id,
                subject_id,
                semester,
                section
            ))

            db.commit()

            flash(
                "Faculty workload assigned successfully.",
                "success"
            )

    # Faculty List
    cursor.execute("""
        SELECT faculty_id, faculty_name
        FROM faculty
        ORDER BY faculty_name
    """)
    faculty_list = cursor.fetchall()

    # Department List
    cursor.execute("""
        SELECT department_id, department_name
        FROM departments
        ORDER BY department_name
    """)
    department_list = cursor.fetchall()

    # Subject List
    cursor.execute("""
        SELECT subject_id, subject_name
        FROM subjects
        ORDER BY subject_name
    """)
    subject_list = cursor.fetchall()

    # Existing Workloads
    cursor.execute("""
        SELECT
            fw.workload_id,
            f.faculty_name,
            d.department_name,
            s.subject_name,
            fw.semester,
            fw.section
        FROM faculty_workload fw
        JOIN faculty f
            ON fw.faculty_id=f.faculty_id
        JOIN departments d
            ON fw.department_id=d.department_id
        JOIN subjects s
            ON fw.subject_id=s.subject_id
        ORDER BY f.faculty_name
    """)

    workload_list = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(

        "faculty_workload.html",

        faculty_list=faculty_list,

        department_list=department_list,

        subject_list=subject_list,

        workload_list=workload_list

    )

# =====================================================
# ADMIN LOGOUT
# =====================================================

@admin.route("/admin/logout")
def admin_logout():

    session.clear()

    flash("Logged out successfully.", "success")

    return redirect(url_for("index"))