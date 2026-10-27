from werkzeug.security import generate_password_hash
from config import get_db_connection


def reset_password():
    username = input("Enter student username: ").strip()
    new_password = input("Enter your custom new password: ").strip()

    if not username or not new_password:
        print("Username and password cannot be empty.")
        return

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Check if student exists
    cursor.execute("SELECT * FROM students WHERE username = %s", (username,))
    student = cursor.fetchone()

    if not student:
        print(f"❌ Student username '{username}' not found.")
        cursor.close()
        db.close()
        return

    # Update with new hashed password
    hashed_password = generate_password_hash(new_password)
    cursor.execute(
        "UPDATE students SET password = %s WHERE username = %s",
        (hashed_password, username)
    )
    db.commit()

    print(
        f"✅ Success! Password for '{student['full_name']}' ({username}) "
        f"has been set to: {new_password}"
    )

    cursor.close()
    db.close()


if __name__ == "__main__":
    reset_password()