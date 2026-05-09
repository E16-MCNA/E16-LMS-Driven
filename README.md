# E16 LMS (Premium Data-Driven MVP)

A high-performance, Flask-based Learning Management System designed with a data-first approach for educational analytics.

## 🚀 Features
- **Role-Based Access Control (RBAC):** Distinct workflows for `Students`, `Teachers`, and `Admins`.
- **Learning Analytics:** Real-time tracking of student progress via `LearningLog`.
- **Modern UI:** Premium dark-mode interface with glassmorphism and responsive design.
- **Production Ready:** Dockerized with Gunicorn and PostgreSQL support.

## 🛠️ Tech Stack
- **Backend:** Python 3.12+, Flask, Flask-SQLAlchemy, Flask-Migrate
- **Database:** PostgreSQL (Production), SQLite (Development)
- **Frontend:** HTML5, Vanilla CSS, Chart.js
- **DevOps:** Docker, Docker Compose

## 💻 Installation

### 1. Environment Setup
Clone the repository and create your environment file:
```bash
cp .env.example .env
# Edit .env with your specific secrets
```

### 2. Run with Docker (Recommended)
```bash
docker-compose up --build
```
The app will be available at `http://localhost:5000`.

### 3. Manual Installation
**Windows (PowerShell):**
```powershell
.\start_e16.ps1
```
**Linux/macOS:**
```bash
chmod +x start.sh
./start.sh
```

## 🔒 Security & Deployment
- **Debug Mode:** Managed via `FLASK_DEBUG` environment variable. Never enable in production.
- **Database Seeding:** The `/seed` route is protected. Use `http://your-domain.com/seed?key=YOUR_SEED_PASSWORD`.
- **Database Migrations:** Always use `flask db upgrade` to apply schema changes.

## 📊 Data Analysis (DA) Workflow
The system exports learning logs in CSV format, optimized for integration with BI tools or Python data science libraries.
- Columns: `student_email`, `course_title`, `lesson_title`, `action_type`, `timestamp`.

## 🤝 Handover Notes
To deploy for a client:
1. Set up a managed PostgreSQL instance.
2. Configure `DATABASE_URL` and a strong `SECRET_KEY` in the hosting environment.
3. Map a custom domain with SSL enabled.
4. Run the seed route once to initialize the platform.
