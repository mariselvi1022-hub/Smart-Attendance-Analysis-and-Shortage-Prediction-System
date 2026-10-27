import mysql.connector

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "MySQL@123",
    "database": "smart_attendance_db"
}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)