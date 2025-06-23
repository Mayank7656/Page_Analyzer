from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file, Response
import mysql.connector
import datetime
import uuid
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import shutil
import pytz
import PyPDF2
import random
import string
import time

load_dotenv()

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# Configure upload folders
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_PDF_FOLDER = os.path.join(BASE_DIR, 'pdfs')
ADMIN_PDF_FOLDER = os.path.join(BASE_DIR, 'admin_pdfs')
ALLOWED_EXTENSIONS = {'pdf'}

# Create upload folders if they don't exist
os.makedirs(USER_PDF_FOLDER, exist_ok=True)
os.makedirs(ADMIN_PDF_FOLDER, exist_ok=True)

# Set folder permissions (if on Unix-like system)
if os.name != 'nt':  # Not Windows
    os.chmod(USER_PDF_FOLDER, 0o755)
    os.chmod(ADMIN_PDF_FOLDER, 0o755)

app.config['USER_PDF_FOLDER'] = USER_PDF_FOLDER
app.config['ADMIN_PDF_FOLDER'] = ADMIN_PDF_FOLDER

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '12345',
    'database': 'pdf_analytics'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_random_url():
    # Generate a random URL-safe string
    random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    timestamp = int(time.time())
    return f"{random_string}-{timestamp}"

def sync_pdf_folders():
    try:
        print("\n=== Starting PDF Folder Sync ===")
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get all PDFs from both folders
        admin_files = set(f for f in os.listdir(ADMIN_PDF_FOLDER) if f.endswith('.pdf'))
        user_files = set(f for f in os.listdir(USER_PDF_FOLDER) if f.endswith('.pdf'))
        print(f"Found {len(admin_files)} admin files and {len(user_files)} user files")
        
        # Get all PDFs and their mappings from database
        cursor.execute("""
            SELECT 
                p.filename, 
                p.original_filename, 
                p.unique_url,
                um.public_url,
                um.created_at
            FROM pdfs p
            LEFT JOIN (
                SELECT original_url, public_url, created_at
                FROM url_mappings um1
                WHERE um1.is_active = TRUE
                AND um1.created_at = (
                    SELECT MAX(created_at)
                    FROM url_mappings um2
                    WHERE um2.original_url = um1.original_url
                )
            ) um ON p.unique_url = um.original_url
        """)
        db_files = {row['filename']: row for row in cursor.fetchall()}
        print(f"Found {len(db_files)} files in database")
        
        # Add missing files to database
        for filename in admin_files.union(user_files):
            if filename not in db_files:
                print(f"Processing new file: {filename}")
                # Generate unique URL for new file
                unique_url = str(uuid.uuid4())
                public_url = str(uuid.uuid4())
                
                # Try to extract original filename from the file itself
                original_filename = filename
                if len(filename) > 41:  # UUID length (36) + .pdf (4)
                    original_filename = filename[37:-4]  # Remove UUID and .pdf
                
                # Get total pages
                total_pages = 0
                try:
                    pdf_path = os.path.join(USER_PDF_FOLDER, filename)
                    if not os.path.exists(pdf_path):
                        pdf_path = os.path.join(ADMIN_PDF_FOLDER, filename)
                    
                    with open(pdf_path, 'rb') as pdf_file:
                        pdf_reader = PyPDF2.PdfReader(pdf_file)
                        total_pages = len(pdf_reader.pages)
                    print(f"File has {total_pages} pages")
                except Exception as e:
                    print(f"Error getting total pages for {filename}: {str(e)}")
                
                try:
                    # Insert into pdfs table
                    cursor.execute("""
                        INSERT INTO pdfs (filename, original_filename, unique_url, created_at, total_pages)
                        VALUES (%s, %s, %s, NOW(), %s)
                    """, (filename, original_filename, unique_url, total_pages))
                    
                    # Get the inserted PDF ID
                    pdf_id = cursor.lastrowid
                    
                    # Create URL mapping
                    cursor.execute("""
                        INSERT INTO url_mappings (
                            original_url, 
                            public_url, 
                            created_at, 
                            pdf_id, 
                            original_filename,
                            is_active
                        ) VALUES (%s, %s, NOW(), %s, %s, TRUE)
                    """, (unique_url, public_url, pdf_id, original_filename))
                    
                    print(f"Added new PDF to database: {filename}")
                    conn.commit()
                except Exception as e:
                    print(f"Error adding file to database: {str(e)}")
                    conn.rollback()
        
        conn.close()
        print("=== PDF Folder Sync Completed ===\n")
    except Exception as e:
        print(f"Error syncing PDF folders: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

# Initialize Database
def init_db():
    try:
        print("\n=== Starting Database Initialization ===")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        print("Creating/updating tables...")
        
        # 1. First create admins table
        cursor.execute('''CREATE TABLE IF NOT EXISTS admins 
                          (id INT AUTO_INCREMENT PRIMARY KEY,
                           username VARCHAR(50) NOT NULL UNIQUE,
                           password VARCHAR(255) NOT NULL,
                           created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        print("Admins table ready")
        
        # 2. Create pdfs table
        cursor.execute('''CREATE TABLE IF NOT EXISTS pdfs
                          (id INT AUTO_INCREMENT PRIMARY KEY,
                           filename VARCHAR(255) NOT NULL,
                           original_filename VARCHAR(255) NOT NULL,
                           unique_url VARCHAR(36) NOT NULL UNIQUE,
                           created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                           total_pages INT NOT NULL DEFAULT 0)''')
        print("PDFs table ready")
        
        # 3. Create url_mappings table
        cursor.execute('''CREATE TABLE IF NOT EXISTS url_mappings
                          (id INT AUTO_INCREMENT PRIMARY KEY,
                           original_url VARCHAR(36) NOT NULL,
                           public_url VARCHAR(36) NOT NULL UNIQUE,
                           created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                           is_active BOOLEAN NOT NULL DEFAULT TRUE,
                           last_used DATETIME,
                           pdf_id INT NOT NULL,
                           original_filename VARCHAR(255) NOT NULL,
                           total_views INT NOT NULL DEFAULT 0,
                           last_viewed_at DATETIME,
                           FOREIGN KEY (pdf_id) REFERENCES pdfs(id) ON DELETE CASCADE,
                           FOREIGN KEY (original_url) REFERENCES pdfs(unique_url) ON DELETE CASCADE)''')
        print("URL mappings table ready")
        
        # 4. Create viewing_sessions table
        cursor.execute('''CREATE TABLE IF NOT EXISTS viewing_sessions
                          (id INT AUTO_INCREMENT PRIMARY KEY,
                           session_id VARCHAR(50) NOT NULL,
                           pdf_id INT NOT NULL,
                           public_url VARCHAR(36) NOT NULL,
                           start_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                           end_time DATETIME,
                           total_duration FLOAT NOT NULL DEFAULT 0,
                           total_pages INT NOT NULL DEFAULT 0,
                           unique_pages INT NOT NULL DEFAULT 0,
                           is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                           user_agent VARCHAR(255),
                           ip_address VARCHAR(45),
                           last_activity DATETIME,
                           status ENUM('active', 'completed', 'abandoned') NOT NULL DEFAULT 'active',
                           original_filename VARCHAR(255) NOT NULL,
                           browser VARCHAR(100),
                           device_type VARCHAR(50),
                           operating_system VARCHAR(100),
                           country VARCHAR(100),
                           city VARCHAR(100),
                           is_remote_view BOOLEAN NOT NULL DEFAULT FALSE,
                           email VARCHAR(255),
                           FOREIGN KEY (pdf_id) REFERENCES pdfs(id) ON DELETE CASCADE,
                           FOREIGN KEY (public_url) REFERENCES url_mappings(public_url) ON DELETE CASCADE)''')
        print("Viewing sessions table ready")
        
        # 5. Create page_views table
        cursor.execute('''CREATE TABLE IF NOT EXISTS page_views
                          (id INT AUTO_INCREMENT PRIMARY KEY,
                           session_id INT NOT NULL,
                           pdf_id INT NOT NULL,
                           page_number INT NOT NULL DEFAULT 1,
                           start_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                           end_time DATETIME,
                           duration FLOAT NOT NULL DEFAULT 0,
                           scroll_depth FLOAT NOT NULL DEFAULT 0,
                           zoom_level FLOAT NOT NULL DEFAULT 1.0,
                           time_to_first_view FLOAT,
                           is_complete BOOLEAN NOT NULL DEFAULT FALSE,
                           original_filename VARCHAR(255) NOT NULL,
                           view_count INT NOT NULL DEFAULT 1,
                           last_viewed_at DATETIME,
                           total_time_on_page FLOAT NOT NULL DEFAULT 0,
                           max_scroll_depth FLOAT NOT NULL DEFAULT 0,
                           max_zoom_level FLOAT NOT NULL DEFAULT 1.0,
                           FOREIGN KEY (session_id) REFERENCES viewing_sessions(id) ON DELETE CASCADE,
                           FOREIGN KEY (pdf_id) REFERENCES pdfs(id) ON DELETE CASCADE)''')
        print("Page views table ready")
        
        # Create a default admin user if none exists
        cursor.execute("SELECT COUNT(*) FROM admins")
        admin_count = cursor.fetchone()[0]
        if admin_count == 0:
            cursor.execute("""
                INSERT INTO admins (username, password) 
                VALUES ('admin', 'admin123')
            """)
            print("Created default admin user")
        
        conn.commit()
        print("Database initialized successfully")
        
        # Sync PDF folders after creating tables
        sync_pdf_folders()
        
    except Exception as e:
        print(f"Error in init_db: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise e
    finally:
        if conn:
            conn.close()
    
    print("=== Database Initialization Complete ===\n")

# Admin Login
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'GET':
        return render_template('admin_login.html')
    
    username = request.json.get("username")
    password = request.json.get("password")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM admins WHERE username=%s AND password=%s", (username, password))
    admin = cursor.fetchone()
    conn.close()

    if admin:
        session["admin_logged_in"] = True
        return jsonify({"message": "Login successful", "redirect": "/admin-dashboard"})
    return jsonify({"message": "Invalid credentials"}), 401

# List all PDFs
@app.route('/list-pdfs')
def list_pdfs():
    if not session.get("admin_logged_in"):
        return jsonify({"message": "Unauthorized"}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get sort parameters
        sort_by = request.args.get('sort_by', 'date')
        sort_order = request.args.get('sort_order', 'desc')
        
        # First, get all PDFs with their existing mappings, excluding deleted ones
        query = """
            SELECT 
                p.id, 
                p.original_filename, 
                p.unique_url, 
                p.created_at, 
                p.total_pages,
                COUNT(DISTINCT vs.session_id) as total_sessions,
                COUNT(DISTINCT pv.id) as total_views,
                SUM(pv.duration) as total_duration,
                um.public_url as existing_public_url
            FROM pdfs p
            LEFT JOIN viewing_sessions vs ON p.id = vs.pdf_id
            LEFT JOIN page_views pv ON vs.id = pv.session_id
            LEFT JOIN (
                SELECT original_url, public_url
                FROM url_mappings 
                WHERE is_active = TRUE
            ) um ON p.unique_url = um.original_url
            WHERE p.permanent_delete = FALSE OR p.permanent_delete IS NULL
            GROUP BY p.id, p.original_filename, p.unique_url, p.created_at, p.total_pages, um.public_url
        """
        
        # Add sorting
        if sort_by == 'name':
            query += f" ORDER BY p.original_filename {sort_order}"
        elif sort_by == 'sessions':
            query += f" ORDER BY total_sessions {sort_order}"
        elif sort_by == 'views':
            query += f" ORDER BY total_views {sort_order}"
        elif sort_by == 'duration':
            query += f" ORDER BY total_duration {sort_order}"
        else:  # default to date
            query += f" ORDER BY p.created_at {sort_order}"
            
        cursor.execute(query)
        pdfs = cursor.fetchall()
        
        # Get the server's network address
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            server_host = s.getsockname()[0]
            s.close()
        except Exception as e:
            print(f"Error getting server IP: {str(e)}")
            if request.remote_addr and request.remote_addr != '127.0.0.1':
                server_host = request.remote_addr
            else:
                server_host = "192.168.1.1"
        
        # Get the protocol
        protocol = request.headers.get('X-Forwarded-Proto', 'http')
        
        # Process each PDF
        for pdf in pdfs:
            # Only generate URLs for non-deleted PDFs
            if not pdf.get('existing_public_url'):
                # Generate a new URL only if one doesn't exist
                new_public_url = generate_random_url()
                cursor.execute("""
                    INSERT INTO url_mappings (
                        original_url, 
                        public_url, 
                        created_at, 
                        pdf_id, 
                        original_filename,
                        is_active
                    ) VALUES (%s, %s, NOW(), %s, %s, TRUE)
                """, (pdf['unique_url'], new_public_url, pdf['id'], pdf['original_filename']))
                conn.commit()
                pdf['view_url'] = f"{protocol}://{server_host}/view-pdf/pdfs/{new_public_url}"
            else:
                pdf['view_url'] = f"{protocol}://{server_host}/view-pdf/pdfs/{pdf['existing_public_url']}"
            
            pdf['admin_view_url'] = f"{protocol}://{server_host}/view-pdf/admin/{pdf['unique_url']}"
            
            # Ensure no null values in statistics
            pdf['total_sessions'] = pdf['total_sessions'] or 0
            pdf['total_views'] = pdf['total_views'] or 0
            pdf['total_duration'] = float(pdf['total_duration'] or 0)
            pdf['total_pages'] = pdf['total_pages'] or 0
        
        conn.close()
        return jsonify(pdfs)
    except Exception as e:
        print(f"Error in list_pdfs: {str(e)}")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500

# Upload PDF
@app.route('/upload-pdf', methods=['POST'])
def upload_pdf():
    if not session.get("admin_logged_in"):
        return jsonify({"message": "Unauthorized"}), 401

    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        try:
            # Generate unique identifiers
            unique_url = str(uuid.uuid4())
            unique_filename = f"{unique_url}.pdf"
            original_filename = file.filename  # Store original filename
            
            # Save file in both user and admin folders
            user_file_path = os.path.join(app.config['USER_PDF_FOLDER'], unique_filename)
            admin_file_path = os.path.join(app.config['ADMIN_PDF_FOLDER'], unique_filename)
            
            # Save to user folder
            file.save(user_file_path)
            print(f"File saved to user folder: {user_file_path}")
            
            # Copy to admin folder
            shutil.copy2(user_file_path, admin_file_path)
            print(f"File copied to admin folder: {admin_file_path}")
            
            # Verify files were saved
            if not os.path.exists(user_file_path) or not os.path.exists(admin_file_path):
                return jsonify({"message": "Error saving files"}), 500
            
            # Get total pages from PDF
            total_pages = 0
            try:
                with open(user_file_path, 'rb') as pdf_file:
                    pdf_reader = PyPDF2.PdfReader(pdf_file)
                    total_pages = len(pdf_reader.pages)
                    print(f"Total pages in PDF: {total_pages}")
            except Exception as e:
                print(f"Error getting total pages: {str(e)}")
            
            timestamp = datetime.datetime.now()
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Insert into pdfs table
            cursor.execute("""
                INSERT INTO pdfs (filename, original_filename, unique_url, created_at, total_pages) 
                VALUES (%s, %s, %s, %s, %s)
            """, (unique_filename, original_filename, unique_url, timestamp, total_pages))
            
            # Get the inserted PDF ID
            pdf_id = cursor.lastrowid
            
            # Generate a public URL and insert into url_mappings
            public_url = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO url_mappings (original_url, public_url, created_at, pdf_id, original_filename) 
                VALUES (%s, %s, %s, %s, %s)
            """, (unique_url, public_url, timestamp, pdf_id, original_filename))
            
            conn.commit()
            conn.close()
            
            return jsonify({
                "message": "File uploaded successfully",
                "unique_url": unique_url,
                "view_url": url_for('view_pdf', url_type='pdfs', unique_url=public_url, _external=True),
                "total_pages": total_pages
            })
        except Exception as e:
            print(f"Error in upload_pdf: {str(e)}")
            return jsonify({"message": f"Error uploading file: {str(e)}"}), 500
    
    return jsonify({"message": "Invalid file type"}), 400

# PDF Viewer Page
@app.route('/view-pdf/<url_type>/<unique_url>', methods=['GET', 'POST'])
def view_pdf(url_type, unique_url):
    try:
        print(f"\n=== Starting view_pdf ===")
        print(f"URL Type: {url_type}")
        print(f"Unique URL: {unique_url}")
        print(f"Admin logged in: {session.get('admin_logged_in', False)}")
        
        # Validate URL type
        if url_type not in ['admin', 'pdfs']:
            print(f"Invalid URL type: {url_type}")
            return "Invalid URL type", 400

        # Check if this is an admin view
        is_admin = url_type == 'admin' and session.get("admin_logged_in", False)
        if url_type == 'admin' and not is_admin:
            print("Unauthorized admin access attempt")
            return "Unauthorized", 401

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # For admin view, use the URL directly
            if url_type == 'admin':
                actual_url = unique_url
                print(f"Admin view - Using original URL: {actual_url}")
            else:
                # For user view, check if this is a public URL
                cursor.execute("""
                    SELECT original_url, pdf_id, original_filename 
                    FROM url_mappings 
                    WHERE public_url = %s
                """, (unique_url,))
                mapping = cursor.fetchone()
                
                if not mapping:
                    print(f"No mapping found for public URL: {unique_url}")
                    return "Invalid or expired URL", 404
                
                actual_url = mapping['original_url']
                print(f"Public view - Mapped to original URL: {actual_url}")
            
            # Find the PDF by unique_url
            print(f"Looking for PDF with unique_url: {actual_url}")
            cursor.execute("""
                SELECT p.id as pdf_id, p.filename, p.original_filename, p.unique_url, p.total_pages
                FROM pdfs p
                WHERE p.unique_url = %s
            """, (actual_url,))
            pdf = cursor.fetchone()
            
            if not pdf:
                print(f"PDF not found for URL: {actual_url}")
                return "PDF not found", 404

            print(f"Found PDF: {pdf}")

            # Handle email collection for non-admin views
            if not is_admin:
                if request.method == 'GET':
                    # Show email collection form
                    return render_template('email_form.html', 
                                        pdf_name=pdf['original_filename'],
                                        url_type=url_type,
                                        unique_url=unique_url)
                elif request.method == 'POST':
                    email = request.form.get('email')
                    if not email:
                        return "Email is required", 400

            # Create a session record
            session_id = str(uuid.uuid4())  # Generate a unique session ID
            user_agent = request.headers.get('User-Agent', '')
            ip_address = request.remote_addr
            start_time = get_ist_time()

            # Parse user agent to get device info
            browser = "Unknown"
            device_type = "Unknown"
            operating_system = "Unknown"
            
            if "Windows" in user_agent:
                operating_system = "Windows"
            elif "Mac" in user_agent:
                operating_system = "MacOS"
            elif "Linux" in user_agent:
                operating_system = "Linux"
            elif "Android" in user_agent:
                operating_system = "Android"
            elif "iOS" in user_agent:
                operating_system = "iOS"
            
            if "Mobile" in user_agent:
                device_type = "Mobile"
            elif "Tablet" in user_agent:
                device_type = "Tablet"
            else:
                device_type = "Desktop"
            
            if "Chrome" in user_agent:
                browser = "Chrome"
            elif "Firefox" in user_agent:
                browser = "Firefox"
            elif "Safari" in user_agent:
                browser = "Safari"
            elif "Edge" in user_agent:
                browser = "Edge"

            print(f"Creating session record with ID: {session_id}")
            try:
                cursor.execute("""
                    INSERT INTO viewing_sessions 
                    (session_id, pdf_id, public_url, start_time, total_duration, 
                     total_pages, unique_pages, user_agent, ip_address, last_activity, is_admin,
                     original_filename, browser, device_type, operating_system, email)
                    VALUES (%s, %s, %s, %s, 0, %s, 0, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (session_id, pdf['pdf_id'], unique_url, start_time, pdf['total_pages'],
                     user_agent, ip_address, start_time, is_admin, pdf['original_filename'],
                     browser, device_type, operating_system, email if not is_admin else None))
                conn.commit()
                viewing_session_id = cursor.lastrowid
                print(f"Created viewing session with ID: {viewing_session_id}")
            except Exception as e:
                print(f"Error creating session record: {str(e)}")
                viewing_session_id = None

            # Get the server's network address
            import socket
            try:
                # Get the server's actual IP address
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                server_host = s.getsockname()[0]
                s.close()
                print(f"Detected server IP: {server_host}")
            except Exception as e:
                print(f"Error getting server IP: {str(e)}")
                # Fallback to request.remote_addr if available and not localhost
                if request.remote_addr and request.remote_addr != '127.0.0.1':
                    server_host = request.remote_addr
                else:
                    # If all else fails, use a default IP (you should replace this with your actual server IP)
                    server_host = "192.168.1.1"  # Replace with your actual server IP
            
            # Get the protocol (http or https)
            protocol = request.headers.get('X-Forwarded-Proto', 'http')
            
            # Generate the full URL without port number
            pdf_url = f"{protocol}://{server_host}/serve-online-pdf/{actual_url}"
            print(f"Generated PDF URL: {pdf_url}")

            return render_template('pdf_viewer.html', 
                                filename=pdf_url,
                                original_filename=pdf['original_filename'],
                                unique_url=actual_url,
                                pdf_id=pdf['pdf_id'],
                                viewing_session_id=viewing_session_id or 0,
                                is_admin=is_admin,
                                total_pages=pdf['total_pages'])

        finally:
            conn.close()
            print("=== Completed view_pdf ===\n")
            
    except Exception as e:
        print(f"Error in view_pdf: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return "Internal server error", 500

# Serve PDF file
@app.route('/serve-pdf/<filename>')
def serve_pdf(filename):
    try:
        print(f"\n=== Starting serve_pdf ===")
        print(f"Filename: {filename}")
        url_type = request.args.get('url_type', 'pdfs')
        print(f"URL Type: {url_type}")
        
        # Ensure filename is safe
        safe_filename = secure_filename(filename)
        if safe_filename != filename:
            print(f"Filename sanitized from {filename} to {safe_filename}")
            filename = safe_filename
            
        # Try both folders
        admin_path = os.path.join(app.config['ADMIN_PDF_FOLDER'], filename)
        user_path = os.path.join(app.config['USER_PDF_FOLDER'], filename)
        
        print(f"Checking for PDF at:")
        print(f"Admin path: {admin_path}")
        print(f"User path: {user_path}")
        
        # Determine which path to use
        if url_type == 'admin' and os.path.exists(admin_path):
            file_path = admin_path
        elif url_type == 'pdfs' and os.path.exists(user_path):
            file_path = user_path
        else:
            # Fallback to the other folder if the preferred one doesn't have the file
            file_path = admin_path if os.path.exists(admin_path) else user_path
            
        if not os.path.exists(file_path):
            print("PDF not found in either folder")
            return "PDF file not found", 404
            
        print(f"Serving PDF from: {file_path}")
        return send_file(file_path, mimetype='application/pdf', as_attachment=False)
    except Exception as e:
        print(f"Error in serve_pdf: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return "Internal server error", 500
    finally:
        print("=== Completed serve_pdf ===\n")

@app.route('/serve-remote-pdf/<unique_url>')
def serve_remote_pdf(unique_url):
    try:
        print(f"\n=== Starting serve_remote_pdf ===")
        print(f"Unique URL: {unique_url}")
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Get the PDF information
            cursor.execute("""
                SELECT p.filename, p.original_filename
                FROM pdfs p
                WHERE p.unique_url = %s
            """, (unique_url,))
            pdf = cursor.fetchone()
            
            if not pdf:
                return "PDF not found", 404
            
            # Try to find the PDF in either folder
            admin_path = os.path.join(app.config['ADMIN_PDF_FOLDER'], pdf['filename'])
            user_path = os.path.join(app.config['USER_PDF_FOLDER'], pdf['filename'])
            
            # Determine which path to use
            if os.path.exists(admin_path):
                file_path = admin_path
            elif os.path.exists(user_path):
                file_path = user_path
            else:
                return "PDF file not found", 404
            
            print(f"Serving remote PDF from: {file_path}")
            return send_file(file_path, mimetype='application/pdf', as_attachment=False)
            
        finally:
            conn.close()
            print("=== Completed serve_remote_pdf ===\n")
            
    except Exception as e:
        print(f"Error in serve_remote_pdf: {str(e)}")
        return "Internal server error", 500

@app.route('/serve-online-pdf/<unique_url>')
def serve_online_pdf(unique_url):
    try:
        print(f"\n=== Starting serve_online_pdf ===")
        print(f"Unique URL: {unique_url}")
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Get the PDF information
            cursor.execute("""
                SELECT p.filename, p.original_filename, p.permanent_delete
                FROM pdfs p
                WHERE p.unique_url = %s
            """, (unique_url,))
            pdf = cursor.fetchone()
            
            if not pdf:
                print(f"PDF not found in database for URL: {unique_url}")
                return "PDF not found", 404
                
            if pdf.get('permanent_delete'):
                print(f"PDF has been permanently deleted: {pdf['original_filename']}")
                return "PDF has been permanently deleted", 410
            
            print(f"Found PDF in database: {pdf['original_filename']}")
            
            # Try to find the PDF in either folder
            admin_path = os.path.join(app.config['ADMIN_PDF_FOLDER'], pdf['filename'])
            user_path = os.path.join(app.config['USER_PDF_FOLDER'], pdf['filename'])
            
            print(f"Checking paths:")
            print(f"Admin path: {admin_path} (exists: {os.path.exists(admin_path)})")
            print(f"User path: {user_path} (exists: {os.path.exists(user_path)})")
            
            # Determine which path to use
            if os.path.exists(admin_path):
                file_path = admin_path
                print(f"Using admin path: {file_path}")
            elif os.path.exists(user_path):
                file_path = user_path
                print(f"Using user path: {file_path}")
            else:
                print(f"PDF file not found in either location")
                return "PDF file not found", 404
            
            # Read the PDF file and send it
            try:
                with open(file_path, 'rb') as f:
                    pdf_data = f.read()
                print(f"Successfully read PDF file of size: {len(pdf_data)} bytes")
            except Exception as e:
                print(f"Error reading PDF file: {str(e)}")
                return f"Error reading PDF file: {str(e)}", 500
            
            # Set appropriate headers for PDF streaming
            headers = {
                'Content-Type': 'application/pdf',
                'Content-Disposition': f'inline; filename="{pdf["original_filename"]}"',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Range',
                'Accept-Ranges': 'bytes'
            }
            
            print(f"Serving online PDF: {pdf['original_filename']}")
            return Response(pdf_data, headers=headers)
            
        finally:
            conn.close()
            print("=== Completed serve_online_pdf ===\n")
            
    except Exception as e:
        print(f"Error in serve_online_pdf: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return f"Internal server error: {str(e)}", 500

def get_ist_time():
    """Get current time in Indian Standard Time"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.datetime.now(ist)

@app.route('/log-view', methods=['POST'])
def log_view():
    conn = None
    try:
        data = request.get_json()
        print("\n=== Received Data ===")
        print(f"Raw data: {data}")
        
        if not data:
            print("No data received in request")
            return jsonify({"message": "No data received"}), 400

        viewing_session_id = data.get('viewing_session_id')
        pdf_id = data.get('pdf_id')
        page = data.get('page')
        duration = data.get('duration', 0)
        scroll_depth = data.get('scroll_depth', 0)  # Default to 0 if None
        zoom_level = data.get('zoom_level', 1.0)
        time_to_first_view = data.get('time_to_first_view', 0)
        is_complete = data.get('is_complete', False)
        update_duration = data.get('update_duration', False)

        # Ensure scroll_depth is not None
        if scroll_depth is None:
            scroll_depth = 0

        # Get client information
        user_agent = request.headers.get('User-Agent', '')
        ip_address = request.remote_addr

        print("\n=== Parsed Data ===")
        print(f"Session ID: {viewing_session_id}")
        print(f"PDF ID: {pdf_id}")
        print(f"Page: {page}")
        print(f"Duration: {duration}")
        print(f"Scroll Depth: {scroll_depth}")
        print(f"Zoom Level: {zoom_level}")
        print(f"Time to First View: {time_to_first_view}")
        print(f"Is Complete: {is_complete}")
        print(f"Update Duration: {update_duration}")
        print(f"User Agent: {user_agent}")
        print(f"IP Address: {ip_address}")
        print("===================\n")

        # Validate required fields
        if not viewing_session_id or not pdf_id or page is None:
            print("Missing required fields")
            return jsonify({"message": "Missing required fields"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Verify the viewing session exists and get its data
            cursor.execute("""
                SELECT id, pdf_id, session_id, total_pages 
                FROM viewing_sessions 
                WHERE id = %s
            """, (viewing_session_id,))
            session = cursor.fetchone()
            if not session:
                print(f"Viewing session not found: {viewing_session_id}")
                return jsonify({"message": "Viewing session not found"}), 404

            # Use the PDF ID from the session if not provided
            if not pdf_id:
                pdf_id = session[1]

            # If this is a completion signal, update session status
            if is_complete:
                print("Processing completion signal")
                # First update the current page view
                cursor.execute("""
                    UPDATE page_views 
                    SET duration = %s,
                        scroll_depth = GREATEST(scroll_depth, %s),
                        zoom_level = GREATEST(zoom_level, %s),
                        end_time = NOW(),
                        is_complete = TRUE
                    WHERE session_id = %s AND page_number = %s
                """, (duration, scroll_depth, zoom_level, viewing_session_id, page))
                
                # Then update the session status
                cursor.execute("""
                    UPDATE viewing_sessions 
                    SET status = 'completed',
                        end_time = NOW(),
                        last_activity = NOW(),
                        total_duration = (
                            SELECT COALESCE(SUM(duration), 0)
                            FROM page_views
                            WHERE session_id = %s
                        ),
                        total_pages = %s,
                        unique_pages = (
                            SELECT COUNT(DISTINCT page_number)
                            FROM page_views
                            WHERE session_id = %s
                        )
                    WHERE id = %s
                """, (viewing_session_id, session[3], viewing_session_id, viewing_session_id))
                
                conn.commit()
                print("Session marked as completed")
                return jsonify({'status': 'success', 'message': 'Session completed'})

            # Check if this is a duration update for a revisited page
            if update_duration:
                print("Processing duration update")
                # Update the duration for the existing page view
                cursor.execute("""
                    UPDATE page_views 
                    SET duration = %s,
                        scroll_depth = GREATEST(scroll_depth, %s),
                        zoom_level = GREATEST(zoom_level, %s),
                        end_time = NOW()
                    WHERE session_id = %s AND page_number = %s
                """, (duration, scroll_depth, zoom_level, viewing_session_id, page))
                
                # Update session total duration
                cursor.execute("""
                    UPDATE viewing_sessions 
                    SET total_duration = (
                        SELECT COALESCE(SUM(duration), 0)
                        FROM page_views
                        WHERE session_id = %s
                    ),
                    last_activity = NOW()
                    WHERE id = %s
                """, (viewing_session_id, viewing_session_id))
                
                conn.commit()
                print("Duration updated successfully")
                return jsonify({'status': 'success', 'message': 'Duration updated'})

            # For new page views, check if this page has been viewed in this session
            print("Processing new page view")
            cursor.execute("""
                SELECT COUNT(*) 
                FROM page_views 
                WHERE session_id = %s AND page_number = %s
            """, (viewing_session_id, page))
            page_count = cursor.fetchone()[0]
            is_new_page = page_count == 0

            if is_new_page:
                print("Inserting new page view")
                # Get the original filename from the PDF
                cursor.execute("SELECT original_filename, total_pages FROM pdfs WHERE id = %s", (pdf_id,))
                pdf = cursor.fetchone()
                if not pdf:
                    return jsonify({"message": "PDF not found"}), 404

                # Insert new page view
                cursor.execute("""
                    INSERT INTO page_views (
                        session_id, pdf_id, page_number, duration, 
                        scroll_depth, zoom_level, time_to_first_view, is_complete,
                        start_time, end_time, original_filename
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s)
                """, (
                    viewing_session_id, pdf_id, page, duration, 
                    scroll_depth, zoom_level, time_to_first_view, is_complete,
                    pdf[0]  # original_filename
                ))

                # Update session statistics
                cursor.execute("""
                    UPDATE viewing_sessions 
                    SET total_duration = (
                        SELECT COALESCE(SUM(duration), 0)
                        FROM page_views
                        WHERE session_id = %s
                    ),
                    total_pages = %s,
                    unique_pages = (
                        SELECT COUNT(DISTINCT page_number)
                        FROM page_views
                        WHERE session_id = %s
                    ),
                    last_activity = NOW()
                    WHERE id = %s
                """, (viewing_session_id, pdf[1], viewing_session_id, viewing_session_id))
                
                conn.commit()
                print("New page view logged successfully")

            return jsonify({
                'status': 'success',
                'is_new_page': is_new_page,
                'message': 'Page view logged successfully'
            })

        except mysql.connector.Error as e:
            conn.rollback()
            print(f"Database error in log_view: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Database error: {str(e)}'}), 500
        except Exception as e:
            conn.rollback()
            print(f"Unexpected error in log_view: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Unexpected error: {str(e)}'}), 500

    except Exception as e:
        print(f"Error in log_view: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        if conn:
            conn.close()

# Get sessions for a PDF
@app.route('/get-sessions/<unique_url>')
def get_sessions(unique_url):
    if not session.get("admin_logged_in"):
        return jsonify({"message": "Unauthorized"}), 401

    conn = None
    try:
        print(f"\n=== Starting get_sessions for URL: {unique_url} ===")
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # First verify the PDF exists and get its ID
        cursor.execute("SELECT id FROM pdfs WHERE unique_url = %s", [unique_url])
        pdf = cursor.fetchone()
        
        if not pdf:
            print(f"PDF not found for URL: {unique_url}")
            return jsonify([])
        
        pdf_id = pdf['id']
        print(f"Found PDF with ID: {pdf_id}")
        
        # Get all sessions
        cursor.execute("""
            SELECT * FROM viewing_sessions 
            WHERE pdf_id = %s AND is_admin = FALSE
            ORDER BY start_time DESC
        """, [pdf_id])
        
        sessions = cursor.fetchall()
        print(f"Found {len(sessions)} sessions")
        
        # Now get page views for each session
        formatted_sessions = []
        for session_data in sessions:
            try:
                session_id = session_data['id']
                cursor.execute("""
                    SELECT page_number, duration 
                    FROM page_views 
                    WHERE session_id = %s
                """, [session_id])
                
                page_views = cursor.fetchall()
                
                # Convert to page durations dictionary
                page_durations = {}
                for pv in page_views:
                    page_num = int(pv['page_number'])
                    duration = float(pv['duration'] or 0)
                    page_durations[page_num] = duration
                
                # Format the session data
                formatted_session = {
                    'session_id': session_data['session_id'],
                    'start_time': session_data['start_time'].strftime('%Y-%m-%d %H:%M:%S'),
                    'duration': float(session_data['total_duration'] or 0),
                    'total_pages': int(session_data['total_pages'] or 0),
                    'unique_pages': int(session_data['unique_pages'] or 0),
                    'status': session_data['status'] or 'unknown',
                    'browser': session_data['browser'] or 'Unknown',
                    'device_type': session_data['device_type'] or 'Unknown',
                    'operating_system': session_data['operating_system'] or 'Unknown',
                    'email': session_data['email'] or 'Not provided',
                    'page_durations': page_durations
                }
                formatted_sessions.append(formatted_session)
                
            except Exception as e:
                print(f"Error processing session {session_data.get('session_id', 'unknown')}: {str(e)}")
                import traceback
                print(f"Traceback: {traceback.format_exc()}")
                continue
        
        print(f"Successfully formatted {len(formatted_sessions)} sessions")
        return jsonify(formatted_sessions)
        
    except Exception as e:
        print(f"Error in get_sessions: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()
            print("=== Completed get_sessions ===\n")

@app.route('/get-session-details/<user_session>')
def get_session_details(user_session):
    if not session.get("admin_logged_in"):
        return jsonify({"message": "Unauthorized"}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get all views for this session with proper time formatting
        cursor.execute("""
            SELECT 
                pv.page_number,
                pv.duration,
                pv.scroll_depth,
                pv.zoom_level,
                pv.is_complete,
                p.original_filename,
                p.unique_url,
                p.total_pages,
                um.public_url,
                vs.total_duration as session_duration,
                vs.browser,
                vs.device_type,
                vs.operating_system,
                DATE_FORMAT(CONVERT_TZ(pv.start_time, 'UTC', 'Asia/Kolkata'), '%Y-%m-%d %H:%i:%s') as formatted_start_time,
                DATE_FORMAT(CONVERT_TZ(pv.end_time, 'UTC', 'Asia/Kolkata'), '%Y-%m-%d %H:%i:%s') as formatted_end_time
            FROM page_views pv
            JOIN viewing_sessions vs ON pv.session_id = vs.id
            JOIN pdfs p ON vs.pdf_id = p.id
            LEFT JOIN url_mappings um ON p.unique_url = um.original_url
            WHERE vs.session_id = %s AND vs.is_admin = FALSE
            ORDER BY pv.start_time ASC
        """, (user_session,))
        views = cursor.fetchall()
        
        # Format the data for the graph
        graph_data = {
            'pages': [],
            'durations': [],
            'start_times': [],
            'end_times': [],
            'scroll_depths': [],
            'zoom_levels': []
        }
        
        session_info = None
        if views:
            first_view = views[0]
            session_info = {
                'pdf_name': first_view['original_filename'],
                'total_pages': first_view['total_pages'],
                'session_duration': float(first_view['session_duration']),
                'browser': first_view['browser'],
                'device_type': first_view['device_type'],
                'operating_system': first_view['operating_system']
            }
        
        for view in views:
            graph_data['pages'].append(view['page_number'])
            graph_data['durations'].append(float(view['duration']))
            graph_data['start_times'].append(view['formatted_start_time'])
            graph_data['end_times'].append(view['formatted_end_time'])
            graph_data['scroll_depths'].append(float(view['scroll_depth']))
            graph_data['zoom_levels'].append(float(view['zoom_level']))
        
        conn.close()
        return jsonify({
            'session_info': session_info,
            'views': views,
            'graph_data': graph_data
        })
    except Exception as e:
        print(f"Error in get_session_details: {str(e)}")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500

# Admin Dashboard to View Analytics
@app.route('/admin-dashboard')
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    conn = None
    try:
        print("\n=== Starting admin_dashboard ===")
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get list of PDFs with proper error handling
        try:
            print("Fetching PDFs list...")
            cursor.execute("""
                SELECT 
                    p.id, 
                    p.original_filename, 
                    p.unique_url, 
                    p.created_at,
                    COALESCE(COUNT(DISTINCT vs.session_id), 0) as total_sessions,
                    COALESCE(COUNT(DISTINCT pv.id), 0) as total_views,
                    COALESCE(SUM(pv.duration), 0) as total_duration,
                    COALESCE(COUNT(DISTINCT pv.page_number), 0) as unique_pages
                FROM pdfs p
                LEFT JOIN viewing_sessions vs ON p.id = vs.pdf_id AND vs.is_admin = FALSE
                LEFT JOIN page_views pv ON vs.id = pv.session_id
                WHERE p.permanent_delete = FALSE OR p.permanent_delete IS NULL
                GROUP BY 
                    p.id, 
                    p.original_filename, 
                    p.unique_url, 
                    p.created_at
                ORDER BY p.created_at DESC
            """)
            pdfs = cursor.fetchall()
            print(f"Found {len(pdfs)} PDFs")
        except Exception as e:
            print(f"Error fetching PDFs: {str(e)}")
            raise
        
        # Get server information for URL generation
        try:
            print("Getting server information...")
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            server_host = s.getsockname()[0]
            s.close()
            print(f"Server host: {server_host}")
        except Exception as e:
            print(f"Error getting server IP: {str(e)}")
            if request.remote_addr and request.remote_addr != '127.0.0.1':
                server_host = request.remote_addr
            else:
                server_host = "192.168.1.1"
        
        # Get the protocol
        protocol = request.headers.get('X-Forwarded-Proto', 'http')
        
        # Process PDFs and generate new URLs for each
        try:
            print("Processing PDFs and generating new URLs...")
            for pdf in pdfs:
                # Generate a new URL for each PDF on every page load
                new_public_url = generate_random_url()
                
                # Deactivate old URL mappings
                cursor.execute("""
                    UPDATE url_mappings 
                    SET is_active = FALSE 
                    WHERE original_url = %s
                """, (pdf['unique_url'],))
                
                # Create new URL mapping
                cursor.execute("""
                    INSERT INTO url_mappings (
                        original_url, 
                        public_url, 
                        created_at, 
                        pdf_id, 
                        original_filename,
                        is_active
                    ) VALUES (%s, %s, NOW(), %s, %s, TRUE)
                """, (pdf['unique_url'], new_public_url, pdf['id'], pdf['original_filename']))
                
                pdf['view_url'] = f"{protocol}://{server_host}/view-pdf/pdfs/{new_public_url}"
                pdf['admin_view_url'] = f"{protocol}://{server_host}/view-pdf/admin/{pdf['unique_url']}"
                
                # Ensure no null values
                pdf['total_sessions'] = int(pdf['total_sessions'] or 0)
                pdf['total_views'] = int(pdf['total_views'] or 0)
                pdf['total_duration'] = float(pdf['total_duration'] or 0)
                pdf['unique_pages'] = int(pdf['unique_pages'] or 0)
            
            conn.commit()
            print("Successfully processed all PDFs and generated new URLs")
        except Exception as e:
            print(f"Error processing PDFs: {str(e)}")
            conn.rollback()
            raise
        
        print("=== Completed admin_dashboard successfully ===\n")
        return render_template('admin_dashboard.html', 
                             pdfs=pdfs)
                             
    except Exception as e:
        print(f"Error in admin_dashboard: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return "Internal server error", 500
    finally:
        if conn:
            conn.close()

@app.route('/')
def home():
    return redirect(url_for('admin_login'))

@app.route('/delete-pdf/<unique_url>', methods=['DELETE'])
def delete_pdf(unique_url):
    if not session.get("admin_logged_in"):
        return jsonify({"message": "Unauthorized"}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # First get the filename and verify the PDF exists
        cursor.execute("SELECT filename, original_filename FROM pdfs WHERE unique_url = %s", (unique_url,))
        pdf = cursor.fetchone()
        
        if not pdf:
            conn.close()
            return jsonify({"message": "PDF not found"}), 404

        try:
            # Mark the PDF as permanently deleted
            cursor.execute("""
                UPDATE pdfs 
                SET permanent_delete = TRUE,
                    deleted_at = NOW()
                WHERE unique_url = %s
            """, (unique_url,))
            
            # Also deactivate any URL mappings for this PDF
            cursor.execute("""
                UPDATE url_mappings 
                SET is_active = FALSE 
                WHERE original_url = %s
            """, (unique_url,))
            
            conn.commit()
            print(f"Successfully marked PDF as permanently deleted: {pdf['original_filename']}")
        except Exception as e:
            print(f"Error updating database: {str(e)}")
            conn.rollback()
            return jsonify({"message": f"Error deleting PDF: {str(e)}"}), 500
        finally:
            conn.close()
        
        return jsonify({
            "message": "PDF deleted successfully",
            "filename": pdf['original_filename']
        })
    except Exception as e:
        print(f"Unexpected error in delete_pdf: {str(e)}")
        return jsonify({"message": f"Error deleting PDF: {str(e)}"}), 500

# Update CORS headers and add cache control
@app.after_request
def after_request(response):
    # Add CORS headers
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,Range')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Expose-Headers', 'Content-Range,Content-Length,Content-Type')
    
    # Add cache control headers
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response

@app.route('/get-pdf-analytics/<unique_url>')
def get_pdf_analytics(unique_url):
    if not session.get("admin_logged_in"):
        return jsonify({"message": "Unauthorized"}), 401

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get PDF info
        cursor.execute("""
            SELECT id, original_filename 
            FROM pdfs 
            WHERE unique_url = %s
        """, (unique_url,))
        pdf = cursor.fetchone()
        
        if not pdf:
            return jsonify({"message": "PDF not found"}), 404
            
        # Get sessions first
        cursor.execute("""
            SELECT 
                vs.id as session_id,
                vs.session_id as unique_session_id,
                vs.start_time,
                vs.end_time,
                COALESCE(vs.total_duration, 0) as total_duration,
                COALESCE(vs.total_pages, 0) as total_pages,
                COALESCE(vs.unique_pages, 0) as unique_pages,
                COALESCE(vs.status, 'unknown') as status,
                COALESCE(vs.browser, 'Unknown') as browser,
                COALESCE(vs.device_type, 'Unknown') as device_type,
                COALESCE(vs.operating_system, 'Unknown') as operating_system,
                DATE_FORMAT(CONVERT_TZ(vs.start_time, 'UTC', 'Asia/Kolkata'), '%Y-%m-%d %H:%i:%s') as formatted_start_time,
                DATE_FORMAT(CONVERT_TZ(vs.end_time, 'UTC', 'Asia/Kolkata'), '%Y-%m-%d %H:%i:%s') as formatted_end_time
            FROM viewing_sessions vs
            WHERE vs.pdf_id = %s AND vs.is_admin = FALSE
            ORDER BY vs.start_time DESC
        """, (pdf['id'],))
        sessions = cursor.fetchall()
        
        # Convert datetime objects to strings for JSON serialization
        for session in sessions:
            if isinstance(session['start_time'], datetime.datetime):
                session['start_time'] = session['start_time'].strftime('%Y-%m-%d %H:%M:%S')
            if isinstance(session['end_time'], datetime.datetime):
                session['end_time'] = session['end_time'].strftime('%Y-%m-%d %H:%M:%S')
            
            # Ensure numeric values are properly formatted
            session['total_duration'] = float(session['total_duration'] or 0)
            session['total_pages'] = int(session['total_pages'] or 0)
            session['unique_pages'] = int(session['unique_pages'] or 0)
        
        # For each session, get its page analytics
        for session in sessions:
            cursor.execute("""
                SELECT 
                    pv.page_number,
                    COALESCE(pv.duration, 0) as duration,
                    COALESCE(pv.scroll_depth, 0) as scroll_depth,
                    COALESCE(pv.zoom_level, 1.0) as zoom_level,
                    COALESCE(pv.time_to_first_view, 0) as time_to_first_view,
                    pv.is_complete,
                    DATE_FORMAT(CONVERT_TZ(pv.start_time, 'UTC', 'Asia/Kolkata'), '%Y-%m-%d %H:%i:%s') as formatted_start_time,
                    DATE_FORMAT(CONVERT_TZ(pv.end_time, 'UTC', 'Asia/Kolkata'), '%Y-%m-%d %H:%i:%s') as formatted_end_time
                FROM page_views pv
                WHERE pv.session_id = %s
                ORDER BY pv.page_number
            """, (session['session_id'],))
            page_analytics = cursor.fetchall()
            
            # Convert decimal values to float for JSON serialization
            for page in page_analytics:
                page['duration'] = float(page['duration'] or 0)
                page['scroll_depth'] = float(page['scroll_depth'] or 0)
                page['zoom_level'] = float(page['zoom_level'] or 1.0)
                page['time_to_first_view'] = float(page['time_to_first_view'] or 0)
            
            session['page_analytics'] = page_analytics
            
            # Calculate session statistics
            total_views = len(page_analytics)
            avg_duration = sum(float(page['duration'] or 0) for page in page_analytics) / total_views if total_views > 0 else 0
            avg_scroll_depth = sum(float(page['scroll_depth'] or 0) for page in page_analytics) / total_views if total_views > 0 else 0
            
            session['statistics'] = {
                'total_views': total_views,
                'avg_duration': float(avg_duration),
                'avg_scroll_depth': float(avg_scroll_depth)
            }
        
        # Get time-based analytics
        cursor.execute("""
            SELECT 
                DATE(CONVERT_TZ(vs.start_time, 'UTC', 'Asia/Kolkata')) as date,
                COUNT(DISTINCT vs.session_id) as sessions,
                COUNT(DISTINCT pv.id) as views,
                COALESCE(AVG(pv.duration), 0) as avg_duration
            FROM viewing_sessions vs
            LEFT JOIN page_views pv ON vs.id = pv.session_id
            WHERE vs.pdf_id = %s AND vs.is_admin = FALSE
            GROUP BY DATE(CONVERT_TZ(vs.start_time, 'UTC', 'Asia/Kolkata'))
            ORDER BY date DESC
            LIMIT 30
        """, (pdf['id'],))
        time_analytics = cursor.fetchall()
        
        # Convert date objects and decimal values for JSON serialization
        for stat in time_analytics:
            if isinstance(stat['date'], datetime.date):
                stat['date'] = stat['date'].strftime('%Y-%m-%d')
            stat['avg_duration'] = float(stat['avg_duration'] or 0)
        
        # Get device analytics
        cursor.execute("""
            SELECT 
                COALESCE(device_type, 'Unknown') as device_type,
                COALESCE(browser, 'Unknown') as browser,
                COALESCE(operating_system, 'Unknown') as operating_system,
                COUNT(*) as count
            FROM viewing_sessions
            WHERE pdf_id = %s AND is_admin = FALSE
            GROUP BY device_type, browser, operating_system
        """, (pdf['id'],))
        device_analytics = cursor.fetchall()
        
        # Convert count to int for JSON serialization
        for device in device_analytics:
            device['count'] = int(device['count'])
        
        response_data = {
            'pdf_info': pdf,
            'sessions': sessions,
            'time_analytics': time_analytics,
            'device_analytics': device_analytics
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error in get_pdf_analytics: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/get-session-analytics/<unique_url>')
def get_session_analytics(unique_url):
    if not session.get("admin_logged_in"):
        return jsonify({"message": "Unauthorized"}), 401

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # First get the PDF ID
        cursor.execute("SELECT id FROM pdfs WHERE unique_url = %s", (unique_url,))
        pdf = cursor.fetchone()
        
        if not pdf:
            return jsonify({"message": "PDF not found"}), 404
        
        # Get all sessions for this PDF with proper end time calculation
        cursor.execute("""
            SELECT 
                vs.id,
                vs.session_id,
                vs.start_time,
                COALESCE(vs.end_time, 
                    (SELECT MAX(pv.end_time) 
                     FROM page_views pv 
                     WHERE pv.session_id = vs.id)
                ) as end_time,
                vs.total_duration,
                vs.total_pages,
                vs.unique_pages,
                vs.browser,
                vs.device_type,
                vs.operating_system,
                vs.email
            FROM viewing_sessions vs
            WHERE vs.pdf_id = %s AND vs.is_admin = FALSE
            ORDER BY vs.start_time DESC
        """, (pdf['id'],))
        
        sessions = []
        for session_data in cursor.fetchall():
            # Get page views for this session
            cursor.execute("""
                SELECT 
                    page_number,
                    duration,
                    zoom_level,
                    time_to_first_view,
                    start_time,
                    COALESCE(end_time, 
                        (SELECT MAX(end_time) 
                         FROM page_views 
                         WHERE session_id = %s AND page_number = page_views.page_number)
                    ) as end_time
                FROM page_views 
                WHERE session_id = %s 
                ORDER BY page_number
            """, (session_data['id'], session_data['id']))
            
            page_views = []
            for view in cursor.fetchall():
                page_views.append({
                    'page_number': view['page_number'],
                    'duration': float(view['duration'] if view['duration'] else 0),
                    'zoom_level': float(view['zoom_level'] if view['zoom_level'] else 1.0),
                    'time_to_first_view': float(view['time_to_first_view'] if view['time_to_first_view'] else 0),
                    'start_time': view['start_time'].strftime('%Y-%m-%d %H:%M:%S') if view['start_time'] else None,
                    'end_time': view['end_time'].strftime('%Y-%m-%d %H:%M:%S') if view['end_time'] else None
                })
            
            # Calculate session statistics
            total_duration = float(session_data['total_duration'] if session_data['total_duration'] else 0)
            avg_duration = sum(v['duration'] for v in page_views) / len(page_views) if page_views else 0
            
            sessions.append({
                'session_id': session_data['session_id'],
                'start_time': session_data['start_time'].strftime('%Y-%m-%d %H:%M:%S') if session_data['start_time'] else None,
                'end_time': session_data['end_time'].strftime('%Y-%m-%d %H:%M:%S') if session_data['end_time'] else None,
                'total_duration': total_duration,
                'total_pages': int(session_data['total_pages'] if session_data['total_pages'] else 0),
                'unique_pages': int(session_data['unique_pages'] if session_data['unique_pages'] else 0),
                'browser': session_data['browser'] or 'Unknown',
                'device_type': session_data['device_type'] or 'Unknown',
                'operating_system': session_data['operating_system'] or 'Unknown',
                'email': session_data['email'] or 'Not provided',
                'statistics': {
                    'avg_duration': float(avg_duration),
                    'total_views': len(page_views)
                },
                'page_views': page_views
            })
        
        return jsonify({'sessions': sessions})
        
    except Exception as e:
        print(f"Error in get_session_analytics: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/update-session-end', methods=['POST'])
def update_session_end():
    try:
        session_id = session.get('session_id')
        if session_id:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE viewing_sessions 
                SET end_time = NOW() 
                WHERE session_id = %s AND end_time IS NULL
            ''', (session_id,))
            conn.commit()
            cursor.close()
            conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == "__main__":
    init_db()
    try:
        # Get the server's IP address
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            server_ip = s.getsockname()[0]
            s.close()
            print(f"Server IP: {server_ip}")
            # Run the app on the network IP with port 80 (more Linux-friendly)
            app.run(host=server_ip, port=80, debug=True, use_reloader=False)
        except Exception as e:
            print(f"Error getting server IP: {str(e)}")
            # Fallback to default configuration
            app.run(debug=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        print("Server stopped.")
