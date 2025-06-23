# 📄 PDF Analytics Web Application

A Flask-based web application that allows administrators to upload PDFs, generate shareable links, and track detailed user engagement through session and page-level analytics.

---

## 📘 About This Project

This project enables detailed tracking of user interactions with PDF documents. Admins can upload files, share them securely, and monitor how viewers engage — including view durations, scroll depth, zoom level, and more.

---

## ✨ Features

- 🔐 **Admin Login & Session Management**
- 📤 **PDF Upload & Storage (user and admin folders)**
- 🔗 **Unique Shareable URLs**
- 📊 **Page-Level and Session-Level Analytics**
- 📈 **Dashboard with Sorting, Filtering & Metrics**
- 🔎 **Viewer Insights (IP, Device, OS, Browser)**
- 🗑️ **PDF Deletion with Cleanup**
- 🌐 **Dynamic Network IP Detection**

---

## 🛠️ Tech Stack

| Layer       | Technology                  |
|-------------|-----------------------------|
| Backend     | Python, Flask               |
| Database    | MySQL                       |
| Frontend    | HTML, CSS (Jinja Templates) |
| Libraries   | `PyPDF2`, `pytz`, `uuid`, `dotenv`, `mysql-connector-python` |

---

## 🧰 Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/pdf-analytics-app.git
cd pdf-analytics-app
2. Set up virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
3. Install dependencies
pip install -r requirements.txt
If requirements.txt does not exist yet, create it with:
pip freeze > requirements.txt

⚙️ Configuration
1. Create a .env file in the root directory:
SECRET_KEY=your_flask_secret_key
2. Configure MySQL connection
Edit the db_config in app.py:
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'your_password',
    'database': 'pdf_analytics'
}

🧾 Database Setup
Run the app once — the database tables will be automatically created by the init_db() function:
python app.py

Make sure the database pdf_analytics exists in MySQL. You can create it manually:
CREATE DATABASE pdf_analytics;

🚀 Run the Application
python app.py

The app will detect your local network IP and run on it, defaulting to http://<your-local-ip>:80/.

📁 Project Structure
pdf-analytics-app/
│
├── app.py
├── templates/
│   ├── admin_login.html
│   ├── admin_dashboard.html
│   └── pdf_viewer.html
├── pdfs/              # Uploaded PDFs for users
├── admin_pdfs/        # Uploaded PDFs for admin
├── static/            # Optional for CSS/JS
├── .env
└── requirements.txt
🧪 Sample Use Cases
✅ Educational institutes monitoring student activity on course PDFs.

✅ Marketing teams tracking engagement on reports, whitepapers, and case studies.

✅ Internal audits of document usage within organizations.
