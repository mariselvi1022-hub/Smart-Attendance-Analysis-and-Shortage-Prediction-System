from utils.ai_notifier import process_student_ai_alert

# Testing with Student ID 1 (Mariselvi, who has 55.56% in Cloud Computing)
STUDENT_ID = 1

print(f"--- Running AI Attendance Alert Test for Student ID: {STUDENT_ID} ---")
advisory, sent = process_student_ai_alert(STUDENT_ID)

if sent:
    print("\n✅ SUCCESS: Mistral AI recommendation was generated and sent to the student's email!")
    print("\n================= EMAIL CONTENT SENT =================")
    print(advisory)
    print("=======================================================")
else:
    print("\n❌ Failed to send alert. Check terminal logs above.")