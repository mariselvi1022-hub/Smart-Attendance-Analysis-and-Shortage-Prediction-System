import os
import smtplib
from dotenv import load_dotenv

load_dotenv()

smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
smtp_port = int(os.getenv("SMTP_PORT", 587))
smtp_email = os.getenv("SMTP_EMAIL")
smtp_password = os.getenv("SMTP_PASSWORD")

# Replace with the student's actual receiving email
recipient_email = "your_test_receiver@gmail.com" 

print("--- SMTP Configuration Diagnostic ---")
print(f"Server   : {smtp_server}")
print(f"Port     : {smtp_port}")
print(f"Sender   : {smtp_email}")
print(f"Password : {'*' * len(smtp_password) if smtp_password else 'NOT SET'}")
print(f"Receiver : {recipient_email}")
print("--------------------------------------")

try:
    print("1. Connecting to SMTP server...")
    server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
    server.set_debuglevel(1)  # Prints detailed connection output

    print("2. Initiating TLS handshake...")
    server.starttls()

    print("3. Authenticating with Google...")
    server.login(smtp_email, smtp_password)

    print("4. Sending test email...")
    msg = f"From: {smtp_email}\nTo: {recipient_email}\nSubject: Smart Attendance Diagnostic Test\n\nThis is a test notification."
    server.sendmail(smtp_email, recipient_email, msg)
    server.quit()

    print("\n✅ SUCCESS: Test email was successfully sent!")
except smtplib.SMTPAuthenticationError:
    print("\n❌ AUTHENTICATION ERROR: Invalid Gmail address or App Password.")
    print("Make sure you are using a 16-character Google App Password (not your regular Gmail password).")
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")