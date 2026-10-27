from config import db

if db.is_connected():
    print("Connected Successfully!")
else:
    print("Connection Failed!")