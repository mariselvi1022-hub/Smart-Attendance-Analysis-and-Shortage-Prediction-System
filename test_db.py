from models.db import connect_db

db = connect_db()

if db:
    print("Connection Successful")
    db.close()
else:
    print("Connection Failed")