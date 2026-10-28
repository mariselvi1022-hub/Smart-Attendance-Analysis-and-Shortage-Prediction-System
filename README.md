# Smart Attendance Analysis and Shortage Prediction System

An academic attendance monitoring and decision-support web application that automates period-wise attendance logging, evaluates the 75% statutory benchmark, computes consecutive class recovery requirements, and delivers multi-channel proactive shortage notifications.

## Key Features
- **Role-Based Portals:** Dedicated dashboards for Students, Faculty, and Administrators.
- **Period-Wise Attendance Management:** Daily multi-period marking (P1–P6) with duplicate entry guards and session editing/deletion.
- **Automated Mathematical Recovery Engine:** Computes exact recovery targets ($\max(0, 3T - 4P)$) and safe absence allowances ($\lfloor(4P - 3T)/3\rfloor$).
- **What-If Scenario Simulator:** Allows students to test projected attendance percentages prior to taking planned absences.
- **Fault-Tolerant AI Advisory:** OpenRouter AI integration (`openrouter/free`) with deterministic rule-based local fallback.
- **Multi-Channel Alerts:** Instant mobile push notifications via `ntfy.sh` and formal email notices via SMTP with single-day alert deduplication.
- **Visual Analytics & Reporting:** Interactive Chart.js cohort analytics and downloadable reports in landscape PDF (ReportLab) and Excel (openpyxl).

## Tech Stack
- **Backend:** Python 3.10+, Flask
- **Database:** MySQL Server 8.0 (`mysql-connector-python`)
- **Frontend:** HTML5, CSS3, JavaScript, Bootstrap 5
- **Visualizations:** Chart.js
- **Services:** OpenRouter API, `ntfy.sh`, SMTP
- **Report Generation:** ReportLab, pandas, openpyxl

## Setup & Installation
1. Clone the repository:
   ```bash
   git clone [https://github.com/mariselvi1022-hub/smart-attendance-system.git](https://github.com/mariselvi1022-hub/smart-attendance-system.git)
   cd smart-attendance-system