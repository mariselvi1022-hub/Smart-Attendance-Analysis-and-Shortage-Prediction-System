from utils.ai_notifier import send_alerts_to_all_shortage_students

if __name__ == "__main__":
    print("==================================================")
    print("  SCANNING ALL STUDENTS FOR ATTENDANCE SHORTAGES  ")
    print("==================================================")

    result = send_alerts_to_all_shortage_students()

    print("\n----------------- SUMMARY REPORT -----------------")
    print(f"Total Students Checked  : {result['total_evaluated']}")
    print(f"Students with < 75%     : {result['shortage_count']}")
    print(f"Alert Emails Dispatched : {result['emails_delivered']}")
    print("==================================================")