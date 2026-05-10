<div align="center">

# Great Grace SMS — School Management System
**A comprehensive, secure, and modern digital platform for modern school administration.**

[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Deployed on Render](https://img.shields.io/badge/Deployed%20on-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://render.com/)

> [IMAGE PLACEHOLDER: "Add a full-width screenshot of the landing page or login screen here"]

</div>

---

## 📑 Table of Contents

1. [Overview](#-overview)
2. [Key Features](#-key-features)
3. [Screenshots](#-screenshots)
4. [Tech Stack](#-tech-stack)
5. [System Architecture](#-system-architecture)
6. [Getting Started](#-getting-started)
7. [Usage Guide](#-usage-guide)
8. [Live Demo](#-live-demo)
9. [Roadmap](#-roadmap)
10. [Contributing](#-contributing)
11. [License](#-license)
12. [Author](#-author)

---

## 🎯 Overview

Great Grace SMS is a comprehensive and scalable School Management System built to digitize and streamline the core operations of modern educational institutions. Designed with administrators, teachers, students, and parents in mind, the platform centralizes academic management, student tracking, and automated grading workflows. What makes this system truly unique is its robust, integrated Computer-Based Testing (CBT) engine that features anti-malpractice tracking, automated grading, and an advanced automated report card generation system that aggregates performance across multiple assessment types.

---

## ✨ Key Features

### 🏫 Academics Management
* **Dynamic Hierarchy:** Easily manage academic sessions, terms, class levels (Primary, JSS, SSS), and class arms.
* **Curriculum Mapping:** Assign specific subjects to different class arms and track custom subject offerings.
* **Teacher Allocation:** Seamlessly assign teachers to subjects and class arms for structured academic workflows.

### 👨‍🎓 Student & Guardian Management
* **Comprehensive Profiles:** Maintain detailed student records including medical history, admission numbers, and enrollment tracking.
* **Guardian Portals:** Link students to primary guardians, granting parents portal access to track academic progress.
* **Attendance Tracking:** Keep daily logs of student attendance linked to specific terms and academic sessions.

### 💻 CBT Examination Engine
* **Automated Objective Testing:** Teachers can create multiple-choice exams (supporting images and special characters) that are automatically graded upon submission.
* **Approval Workflows:** Implement strict quality control where exams must be drafted and approved by an examiner before students can access them.
* **Configurable Grading:** School administrators can dynamically configure score weighting (e.g., CA1 20%, CA2 20%, OBJ 30%, Theory 30%) across the entire system.

### 📊 Results & Report Cards
* **Automated Aggregation:** The system automatically aggregates scores from CBT exams and manually graded theory tests to compute final percentages and grades.
* **Termly Report Cards:** Generate comprehensive report cards detailing subject performance, cumulative averages, and attendance statistics.
* **Domain Assessments:** Grade students on affective (punctuality, neatness) and psychomotor (handwriting, sports) domains with teacher and principal comments.

### 🔐 Role-Based Access Control
* **Secure Workflows:** Distinct permissions and tailored dashboards for Principals, Teachers, Students, and Guardians.
* **Strict Data Boundaries:** Teachers can only grade assigned subjects, and students can only view approved exams for their current enrollment.

### 🛡️ Security & Anti-Malpractice
* **Daily Exam PINs:** A unique, daily-generated PIN is required for students to unlock any CBT exam on that specific day.
* **Behavior Monitoring:** The CBT engine actively tracks and logs tab switching and fullscreen exits during an active test to flag potential malpractice.
* **Audit Trails:** A comprehensive result audit log tracks every manual modification to a student's score, recording who made the change, when, and why.

---

## 📸 Screenshots

> [IMAGE PLACEHOLDER: "Screenshot of Dashboard (Principal view) — add image here: /screenshots/principal_dashboard.png"]

> [IMAGE PLACEHOLDER: "Screenshot of Student Portal — add image here: /screenshots/student_portal.png"]

> [IMAGE PLACEHOLDER: "Screenshot of CBT Exam Interface (in progress) — add image here: /screenshots/cbt_exam_interface.png"]

> [IMAGE PLACEHOLDER: "Screenshot of Report Card (generated output) — add image here: /screenshots/report_card_output.png"]

> [IMAGE PLACEHOLDER: "Screenshot of Teacher Grading Panel — add image here: /screenshots/teacher_grading_panel.png"]

> [IMAGE PLACEHOLDER: "Screenshot of Attendance Marking Screen — add image here: /screenshots/attendance_marking.png"]

---

## 🛠 Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Backend** | Python 3.x, Django |
| **Frontend** | HTML5, CSS3, JavaScript, Django Templates |
| **Database** | PostgreSQL (Production), SQLite (Development) |
| **Authentication** | Django Auth, Role-based custom permissions |
| **Deployment** | Render, Gunicorn, Whitenoise (Static files) |
| **Other Tools** | Git, Pillow (Image Processing) |

---

## 🏗 System Architecture

The application is highly modularized into distinct Django applications to ensure separation of concerns and maintainability:

* `academics`: Manages sessions, terms, classes, subjects, and teacher assignments.
* `students`: Handles student profiles, guardian relations, enrollments, and attendance.
* `examinations`: Contains the robust CBT engine, exam workflows, and question management.
* `results`: Aggregates scores, processes grades, and generates automated report cards.
* `staff`: Manages school staff profiles and professional details.
* `promotions`: Handles the logic for promoting students to the next class at the end of a session.
* `portal`: Provides the role-specific dashboard views for end-users.
* `schemes`: Manages schemes of work and curriculum outlines.
* `accounts`: Manages custom user models and role definitions.

### Role System
* **Principal/Admin:** Full oversight, system configuration, exam approval, and report card publishing.
* **Teacher:** Subject management, question drafting, theory grading, and attendance marking.
* **Student:** Exam participation, CBT interface access, and personal result viewing.
* **Guardian:** Tracking student performance, attendance, and accessing published report cards.

---

## 🚀 Getting Started

### Prerequisites
* Python 3.9+
* PostgreSQL (Optional for local development, recommended for production)
* Git

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/great_grace_sms.git
   cd great_grace_sms
   ```

2. **Set up a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Apply database migrations**
   ```bash
   python manage.py migrate
   ```

5. **Create a superuser account**
   ```bash
   python manage.py createsuperuser
   ```

6. **Run the development server**
   ```bash
   python manage.py runserver
   ```
   Visit `http://localhost:8000` in your browser.

### Environment Variables
Create a `.env` file in the root directory based on `.env.example`:

```env
DEBUG=True
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgres://user:password@localhost:5432/dbname
ALLOWED_HOSTS=localhost,127.0.0.1
```

---

## 📖 Usage Guide

### Logging In
Users navigate to the main portal and log in using their assigned credentials. The system automatically routes them to their role-specific dashboard (Admin, Teacher, Student, or Guardian).

### Creating an Exam (Teacher Workflow)
1. Navigate to the **Examinations** panel.
2. Select an assigned subject and class.
3. Add objective questions (with optional images) or upload a theory question file.
4. Submit the exam for approval. Once the Principal approves it, it becomes visible to students during the scheduled time.

### Taking a CBT Exam (Student Workflow)
1. Log into the Student Portal.
2. Enter the **Daily Exam PIN** provided by the school administrator.
3. Select an available exam. The timer will start immediately.
4. Answer questions within the secure environment (avoiding tab switches to prevent malpractice flagging) and submit.

### Generating a Report Card (Principal Workflow)
1. Ensure all teachers have completed grading theory and CBT exams for the term.
2. Navigate to the **Results** dashboard.
3. Review the aggregated scores, add principal remarks, and click **Publish**.
4. Report cards instantly become available for students and guardians to download.

---

## 🌐 Live Demo

**Live URL:** [https://great-grace-sms.onrender.com](https://great-grace-sms.onrender.com)
*(Note: Hosted on Render's free tier — please allow 30–60 seconds for the initial cold start.)*

**Demo Credentials:**
* **Username:** `principal`
* **Password:** `password@me`

> [IMAGE PLACEHOLDER: "Add a Loom demo video thumbnail here linked to your demo video URL"]

---

## 🗺 Roadmap

Future enhancements planned for Great Grace SMS:
* [ ] **SMS & Email Notifications:** Automated alerts for parents regarding attendance and published results.
* [ ] **Fee Payment Integration:** Secure online tuition payment gateway directly in the guardian portal.
* [ ] **Mobile App Wrapper:** Cross-platform mobile accessibility for students and parents.
* [ ] **Parent-Teacher Messaging:** In-app communication system to facilitate direct messaging between guardians and educators.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---

## 👤 Author

**Ibraheem Olabintan**
* GitHub: [@yourusername](https://github.com/yourusername)
* LinkedIn: [Ibraheem Olabintan](https://linkedin.com/in/yourlinkedin)
* Email: olabintanibraheem@gmail.com
