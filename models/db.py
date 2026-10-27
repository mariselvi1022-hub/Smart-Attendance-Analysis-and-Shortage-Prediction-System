from config import get_db_connection


def connect_db():
    try:
        connection = get_db_connection()
        print("✅ Connected to MySQL Database")
        return connection

    except Exception as e:
        print("❌ Database Connection Error:", e)
        return None