#############################################################################################################
#                                       Skin Cancer Detection Pro                                           #
#                                       A Python GUI Application                                            #
#############################################################################################################

##############################################################################################################
# Import necessary libraries                                                                                 #
# - customtkinter: Modern GUI framework                                                                     #
# - OpenCV (cv2): Advanced image processing                                                                 #
# - NumPy: Numerical operations                                                                             #
# - PIL: Image handling                                                                                     #
# - psycopg2: PostgreSQL database interaction                                                               #
# - passlib (bcrypt): Password hashing                                                                      #
# - cryptography (Fernet): Data encryption                                                                  #
# - fpdf: PDF report generation                                                                             #
# - webbrowser: Open files                                                                                  #
# - logging: Error tracking and debugging                                                                   #
# - datetime: Timestamp management                                                                          #
# - os, uuid, shutil, tempfile: File and directory operations                                               #
# - config: External configuration (DB_CONFIG, ENCRYPTION_KEY, MAX_IMAGE_SIZE, UPLOAD_DIR)                  #
##############################################################################################################
import os
import uuid
import shutil
import tempfile
import customtkinter as ctk
import cv2
import numpy as np
from PIL import Image, ImageTk
import psycopg2
from passlib.hash import bcrypt
from cryptography.fernet import Fernet
import webbrowser
import logging
from datetime import datetime
from fpdf import FPDF
from config import DB_CONFIG, ENCRYPTION_KEY, MAX_IMAGE_SIZE, UPLOAD_DIR

#############################################################################################################
# Setup logging                                                                                             #
# Logs are written to 'app.log' with timestamp, level, and message for debugging and monitoring.            #
#############################################################################################################
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

#############################################################################################################
# Ensure upload directory exists                                                                            #
# Creates UPLOAD_DIR if it doesn’t exist to store uploaded images securely.                                #
#############################################################################################################
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

#############################################################################################################
# Setup encryption                                                                                          #
# Uses Fernet symmetric encryption with a key from config.py to secure sensitive data like image paths.     #
#############################################################################################################
CIPHER = Fernet(ENCRYPTION_KEY)

###############################################################################################################
# Database Management Class                                                                                   #
# Handles all PostgreSQL interactions: user management, image storage, and analysis tracking.                 #
###############################################################################################################
class Database:
    def __init__(self):
        """Initialize database connection and setup schema."""
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cur = self.conn.cursor()
        self.migrate_schema()
        self.create_tables()

    def migrate_schema(self):
        """Add new columns to existing tables if missing."""
        try:
            self.cur.execute("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS cancer_probability FLOAT")
            self.cur.execute("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS advice TEXT")
            self.cur.execute("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS cancer_type VARCHAR(50)")
            self.conn.commit()
            logging.info("Schema migration completed successfully.")
        except psycopg2.Error as e:
            logging.error(f"Schema migration failed: {e}")
            self.conn.rollback()

    def create_tables(self):
        """Create necessary tables if they don’t exist."""
        table_queries = [
            """CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
            """CREATE TABLE IF NOT EXISTS images (
                image_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
                image_path TEXT NOT NULL,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
            """CREATE TABLE IF NOT EXISTS analyses (
                analysis_id SERIAL PRIMARY KEY,
                image_id INTEGER REFERENCES images(image_id) ON DELETE CASCADE,
                analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                skin_ratio FLOAT,
                cancer_probability FLOAT,
                cancer_type VARCHAR(50),
                advice TEXT)"""
        ]
        for query in table_queries:
            try:
                self.cur.execute(query)
                self.conn.commit()
            except psycopg2.Error as e:
                logging.error(f"Failed to create table: {e}")
                self.conn.rollback()

    def delete_analysis(self, analysis_id):
        """Delete an analysis record by ID."""
        query = "DELETE FROM analyses WHERE analysis_id = %s"
        try:
            self.cur.execute(query, (analysis_id,))
            self.conn.commit()
            return True
        except psycopg2.Error as e:
            logging.error(f"Failed to delete analysis: {e}")
            self.conn.rollback()
            return False

    def insert_user(self, username, password_hash, email):
        """Insert a new user with hashed password."""
        query = """INSERT INTO users (username, password_hash, email)
                   VALUES (%s, %s, %s) RETURNING user_id"""
        try:
            self.cur.execute(query, (username, password_hash, email))
            user_id = self.cur.fetchone()[0]
            self.conn.commit()
            return user_id
        except psycopg2.Error as e:
            logging.error(f"User insertion failed: {e}")
            self.conn.rollback()
            return None

    def get_user_by_username(self, username):
        """Retrieve user data by username."""
        query = "SELECT user_id, username, password_hash, email FROM users WHERE username = %s"
        try:
            self.cur.execute(query, (username,))
            return self.cur.fetchone()
        except psycopg2.Error as e:
            logging.error(f"User retrieval failed: {e}")
            return None

    def insert_image(self, user_id, image_path):
        """Store an encrypted image path linked to a user."""
        encrypted_path = CIPHER.encrypt(image_path.encode()).decode()
        query = "INSERT INTO images (user_id, image_path) VALUES (%s, %s) RETURNING image_id"
        try:
            self.cur.execute(query, (user_id, encrypted_path))
            image_id = self.cur.fetchone()[0]
            self.conn.commit()
            return image_id
        except psycopg2.Error as e:
            logging.error(f"Image insertion failed: {e}")
            self.conn.rollback()
            return None

    def insert_analysis(self, image_id, skin_ratio, cancer_probability, cancer_type, advice):
        """Save analysis results linked to an image."""
        query = """INSERT INTO analyses (image_id, skin_ratio, cancer_probability, cancer_type, advice)
                   VALUES (%s, %s, %s, %s, %s) RETURNING analysis_id"""
        try:
            self.cur.execute(query, (image_id, float(skin_ratio), float(cancer_probability), cancer_type, advice))
            analysis_id = self.cur.fetchone()[0]
            self.conn.commit()
            return analysis_id
        except psycopg2.Error as e:
            logging.error(f"Analysis insertion failed: {e}")
            self.conn.rollback()
            return None

    def get_user_analyses(self, user_id):
        """Retrieve all analyses for a user with decrypted image paths."""
        query = """SELECT a.analysis_id, a.image_id, a.analysis_date, a.skin_ratio,
                          a.cancer_probability, a.cancer_type, a.advice, i.image_path
                   FROM analyses a JOIN images i ON a.image_id = i.image_id
                   WHERE i.user_id = %s"""
        try:
            self.cur.execute(query, (user_id,))
            analyses = []
            for analysis in self.cur.fetchall():
                try:
                    decrypted_path = CIPHER.decrypt(analysis[7].encode()).decode()
                except Exception as e:
                    decrypted_path = f"Decryption error: {str(e)}"
                analyses.append((*analysis[:7], decrypted_path))
            return analyses
        except psycopg2.Error as e:
            logging.error(f"Failed to retrieve analyses: {e}")
            return []

    def get_user_registration_date(self, user_id):
        """Get user registration date for reporting."""
        query = "SELECT registration_date FROM users WHERE user_id = %s"
        try:
            self.cur.execute(query, (user_id,))
            result = self.cur.fetchone()
            return result[0].strftime('%Y-%m-%d') if result else "N/A"
        except psycopg2.Error as e:
            logging.error(f"Failed to get registration date: {e}")
            return "N/A"

    def close(self):
        """Close database connection safely."""
        self.cur.close()
        self.conn.close()

###############################################################################################################
# Skin Detection and Cancer Simulation Class                                                                  #
# Enhanced with YCrCb color space for skin detection and simulated cancer features like asymmetry.            #
###############################################################################################################
class SkinDetector:
    def detect_skin(self, image_path):
        """Detect skin areas using YCrCb color space with morphological cleanup."""
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError("Couldn’t load the image file.")

        # Convert to YCrCb color space (better for skin detection)
        ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
        lower_skin = np.array([0, 133, 77], dtype=np.uint8)
        upper_skin = np.array([255, 173, 127], dtype=np.uint8)
        mask = cv2.inRange(ycrcb, lower_skin, upper_skin)

        # Morphological operations to refine mask
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        skin_pixels = cv2.countNonZero(mask)
        total_pixels = image.shape[0] * image.shape[1]
        skin_image = cv2.bitwise_and(image, image, mask=mask)

        return skin_image, skin_pixels / total_pixels

    def detect_cancer(self, image_path):
        """Simulate cancer detection using asymmetry and color variation."""
        image = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Failed to load image for cancer detection.")

        # Convert to grayscale for asymmetry analysis
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        left = gray[:, :width//2]
        right = gray[:, width//2:]
        asymmetry = np.abs(np.mean(left) - np.mean(right)) / 255.0

        # Color variation from RGB channels
        color_variation = np.std(image, axis=(0, 1)) / 255.0
        color_variation = np.mean(color_variation)

        # Simulated probability (arbitrary but more nuanced)
        probability = (asymmetry + color_variation) / 2
        probability = min(max(probability, 0), 1)
        cancer_detected = probability >= 0.3

        # Classify cancer type based on probability
        if probability <= 0.3:
            cancer_type = "No Cancer Detected"
            prevalence = "N/A"
            advice = "No signs of malignancy. Continue with annual skin checks."
            risk_level = "low"
        elif probability <= 0.5:
            cancer_type = "Basal Cell Carcinoma"
            prevalence = "~80% of skin cancers"
            advice = "Basal Cell Carcinoma detected. Common but less severe. Consult a dermatologist."
            risk_level = "low"
        elif probability <= 0.7:
            cancer_type = "Squamous Cell Carcinoma"
            prevalence = "~16% of skin cancers"
            advice = "Squamous Cell Carcinoma detected. Moderate risk. See a dermatologist soon."
            risk_level = "moderate"
        elif probability <= 0.9:
            cancer_type = "Melanoma"
            prevalence = "~4% of skin cancers"
            advice = "Melanoma detected. High risk. Urgently consult an oncologist within 48 hours."
            risk_level = "high"
        else:
            cancer_type = "Merkel Cell Carcinoma"
            prevalence = "<1% of skin cancers"
            advice = "Merkel Cell Carcinoma detected. Rare and aggressive. Seek immediate attention."
            risk_level = "high"

        advice += "\n\nNote: This is a simulation. Consult a dermatologist for professional diagnosis."
        return probability, cancer_type, prevalence, advice, risk_level, cancer_detected

###############################################################################################################
# PDF Report Generation Class                                                                                 #
# Generates professional PDF reports with patient info, analysis results, and images.                         #
###############################################################################################################
class MedicalReport(FPDF):
    def __init__(self, icon_path='icon.png'):
        super().__init__()
        self.icon_path = icon_path

    def header(self):
        """Add header with icon and timestamp."""
        try:
            self.image(self.icon_path, 10, 8, 33)
        except Exception as e:
            logging.error(f"Couldn’t add icon to PDF: {e}")
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Skin Cancer Detection Report', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1, 'R')
        self.ln(10)

    def footer(self):
        """Add page numbers to footer."""
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def add_report_content(self, user_data, analysis_data, image_path):
        """Fill report with patient info, image, and analysis results."""
        # Patient Info
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Patient Information', 0, 1)
        self.set_font('Arial', '', 12)
        self.cell(0, 10, f'Name: {user_data["username"]}', 0, 1)
        self.cell(0, 10, f'Patient ID: {user_data["user_id"]}', 0, 1)
        self.cell(0, 10, f'Email: {user_data["email"]}', 0, 1)
        self.cell(0, 10, f'Registration Date: {user_data["registration_date"]}', 0, 1)
        self.ln(10)

        # Clinical Image
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Clinical Image', 0, 1)
        try:
            self.image(image_path, x=10, w=180)
            self.ln(100)
        except Exception as e:
            self.set_font('Arial', 'I', 10)
            self.cell(0, 10, f'Image unavailable: {str(e)}', 0, 1)
            self.ln(10)

        # Diagnostic Findings
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Diagnostic Findings', 0, 1)
        self.set_fill_color(240, 240, 240)
        self.set_font('Arial', 'B', 12)
        self.cell(95, 10, 'Parameter', 1, 0, 'C', 1)
        self.cell(95, 10, 'Value', 1, 1, 'C', 1)
        self.set_font('Arial', '', 12)
        metrics = [
            ('Skin Coverage Ratio', f'{analysis_data["skin_ratio"]:.1%}'),
            ('Cancer Probability', f'{analysis_data["cancer_prob"]:.1%}'),
            ('Detected Cancer Type', analysis_data["cancer_type"]),
            ('Prevalence', analysis_data["prevalence"]),
            ('Cancer Detected', 'Yes' if analysis_data["cancer_detected"] else 'No'),
            ('Risk Classification', analysis_data["risk_level"].title()),
            ('Analysis Date', analysis_data["analysis_date"])
        ]
        for param, value in metrics:
            self.cell(95, 10, param, 1)
            self.cell(95, 10, value, 1, 1)

        # Recommendations
        self.ln(10)
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Clinical Recommendations', 0, 1)
        self.set_font('Arial', '', 12)
        self.multi_cell(0, 8, analysis_data["advice"])
        self.ln(5)

        # Disclaimer
        self.ln(10)
        self.set_font('Arial', 'I', 8)
        self.multi_cell(0, 5, analysis_data["disclaimer"])

###############################################################################################################
# GUI Setup                                                                                                   #
# Uses customtkinter with a dark theme for a modern, user-friendly interface.                                #
###############################################################################################################
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

###############################################################################################################
# Login Page                                                                                                  #
# Allows users to log in with their credentials.                                                             #
###############################################################################################################
class LoginPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        frame = ctk.CTkFrame(self, corner_radius=15)
        frame.grid(row=0, column=0, padx=30, pady=30, sticky="nsew")

        ctk.CTkLabel(frame, text="Skin Cancer Detection Pro", font=("Arial", 18, "bold")).pack(pady=20)
        ctk.CTkLabel(frame, text="Patient Login", font=("Arial", 24, "bold")).pack(pady=20)

        self.username = ctk.CTkEntry(frame, placeholder_text="Username", width=250)
        self.username.pack(pady=10)
        self.password = ctk.CTkEntry(frame, placeholder_text="Password", show="*", width=250)
        self.password.pack(pady=10)

        ctk.CTkButton(frame, text="Login", command=self.login, width=250).pack(pady=10)
        ctk.CTkButton(frame, text="Register", command=lambda: self.parent.show_page("RegistrationPage"),
                      width=250, fg_color="transparent", border_width=2).pack(pady=10)

        self.error_label = ctk.CTkLabel(frame, text="", text_color="red")
        self.error_label.pack()

    def login(self):
        """Validate credentials and switch to dashboard."""
        username = self.username.get().strip()
        password = self.password.get()
        if not username or not password:
            self.error_label.configure(text="Please fill all fields")
            return
        user = self.parent.db.get_user_by_username(username)
        if user and bcrypt.verify(password, user[2]):
            self.parent.current_user = {"user_id": user[0], "username": user[1], "email": user[3]}
            self.parent.show_page("DashboardPage")
            logging.info(f"User {username} logged in successfully.")
        else:
            self.error_label.configure(text="Invalid credentials")
            logging.warning(f"Login failed for username: {username}")

###############################################################################################################
# Registration Page                                                                                           #
# Allows new users to create an account with basic input validation.                                         #
###############################################################################################################
class RegistrationPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        frame = ctk.CTkFrame(self, corner_radius=15)
        frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        ctk.CTkLabel(frame, text="Skin Cancer Detection Pro", font=("Arial", 18, "bold")).pack(pady=20)
        ctk.CTkLabel(frame, text="New Patient Registration", font=("Arial", 24, "bold")).pack(pady=20)

        self.username = ctk.CTkEntry(frame, placeholder_text="Username", width=250)
        self.username.pack(pady=10)
        self.email = ctk.CTkEntry(frame, placeholder_text="Email", width=250)
        self.email.pack(pady=10)
        self.password = ctk.CTkEntry(frame, placeholder_text="Password", show="*", width=250)
        self.password.pack(pady=10)

        ctk.CTkButton(frame, text="Register", command=self.register, width=250).pack(pady=10)
        ctk.CTkButton(frame, text="Back to Login", command=lambda: self.parent.show_page("LoginPage"),
                      width=250, fg_color="transparent", border_width=2).pack(pady=10)

        self.status_label = ctk.CTkLabel(frame, text="", text_color="green")
        self.status_label.pack()

    def register(self):
        """Register a new user with validation."""
        username = self.username.get().strip()
        email = self.email.get().strip()
        password = self.password.get()
        if not all([username, email, password]):
            self.status_label.configure(text="All fields required", text_color="red")
            return
        if "@" not in email or "." not in email:
            self.status_label.configure(text="Invalid email format", text_color="red")
            return
        if len(password) < 8:
            self.status_label.configure(text="Password must be at least 8 characters", text_color="red")
            return
        hashed = bcrypt.hash(password)
        user_id = self.parent.db.insert_user(username, hashed, email)
        if user_id:
            self.status_label.configure(text="Registration successful!", text_color="green")
            self.after(2000, lambda: self.parent.show_page("LoginPage"))
            logging.info(f"User {username} registered successfully.")
        else:
            self.status_label.configure(text="Username or email already taken", text_color="red")
            logging.warning(f"Registration failed for {username}: username or email taken.")

###############################################################################################################
# Dashboard Page                                                                                              #
# Main interface for image upload, analysis, and report generation with enhanced feedback and performance.    #
###############################################################################################################
class DashboardPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.image_path = None
        self.analysis_data = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="#2B2B2B")
        header.grid(row=0, column=0, sticky="nsew")
        try:
            icon_img = Image.open("icon.png")
            icon_img = icon_img.resize((40, 40), Image.LANCZOS)
            ctk_icon = ctk.CTkImage(light_image=icon_img, size=(40, 40))
            ctk.CTkLabel(header, image=ctk_icon, text="").pack(side="left", padx=10)
        except Exception as e:
            logging.error(f"Failed to load header icon: {e}")
        ctk.CTkLabel(header, text=f"Patient: {self.parent.current_user['username']}",
                     font=("Arial", 16, "bold")).pack(side="left", padx=20)
        nav_frame = ctk.CTkFrame(header, fg_color="transparent")
        nav_frame.pack(side="right", padx=20)
        ctk.CTkButton(nav_frame, text="History", width=120,
                      command=lambda: self.parent.show_page("HistoryPage")).pack(side="left", padx=5)
        ctk.CTkButton(nav_frame, text="About", width=120,
                      command=lambda: self.parent.show_page("AboutPage")).pack(side="left", padx=5)
        ctk.CTkButton(nav_frame, text="Logout", width=120,
                      fg_color="#3B3B3B", command=self.logout).pack(side="left", padx=5)

        # Main layout
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        main.grid_columnconfigure(0, weight=2)
        main.grid_columnconfigure(1, weight=1)

        # Image display
        self.image_panel = ctk.CTkFrame(main, corner_radius=15)
        self.image_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.image_label = ctk.CTkLabel(self.image_panel, text="Upload Dermatology Image",
                                        font=("Arial", 14), fg_color="#1A1A1A", corner_radius=10)
        self.image_label.pack(expand=True, fill="both", padx=10, pady=10)

        # Controls
        control_panel = ctk.CTkFrame(main, corner_radius=15)
        control_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        ctk.CTkButton(control_panel, text="Upload Image", height=40,
                      font=("Arial", 14), command=self.upload).pack(fill="x", pady=5)
        ctk.CTkButton(control_panel, text="Analyze", height=40,
                      font=("Arial", 14), command=self.analyze).pack(fill="x", pady=5)
        self.save_btn = ctk.CTkButton(control_panel, text="Save Report", height=40,
                                      font=("Arial", 14), state="disabled", command=self.save)
        self.save_btn.pack(fill="x", pady=5)
        ctk.CTkButton(control_panel, text="Export PDF", height=40,
                      font=("Arial", 14), command=self.export_pdf).pack(fill="x", pady=5)

        # Results
        self.results_frame = ctk.CTkFrame(main, height=200, corner_radius=15)
        self.results_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        self.risk_indicator = ctk.CTkLabel(self.results_frame, text="RISK LEVEL",
                                           font=("Arial", 24, "bold"), width=200, height=200,
                                           corner_radius=100)
        self.risk_indicator.pack(side="left", padx=20, pady=20)
        results_text = ctk.CTkFrame(self.results_frame, fg_color="transparent")
        results_text.pack(side="left", fill="both", expand=True)
        self.results_header = ctk.CTkLabel(results_text, text="Analysis Results",
                                           font=("Arial", 18, "bold"))
        self.results_header.pack(anchor="w", pady=5)
        self.results_content = ctk.CTkTextbox(results_text, font=("Arial", 14), wrap="word")
        self.results_content.pack(expand=True, fill="both")

        # Status bar
        self.status_bar = ctk.CTkLabel(self, text="Ready", anchor="w",
                                       font=("Arial", 12), text_color="gray")
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=5)

    def update_risk_indicator(self, risk_level, cancer_detected):
        """Update risk indicator with color and text based on analysis."""
        colors = {"low": ("#2AA876", "LOW RISK"), "moderate": ("#FFC107", "MODERATE RISK"),
                  "high": ("#DC3545", "HIGH RISK")}
        color, text = colors[risk_level]
        if cancer_detected:
            text += " - CANCER DETECTED"
            self.risk_indicator.configure(font=("Arial", 20, "bold"))
        else:
            self.risk_indicator.configure(font=("Arial", 24, "bold"))
        self.risk_indicator.configure(text=text, fg_color=color)
        self.results_header.configure(text_color=color)

    def resize_image(self, image_path, max_size=512):
        """Resize image for faster processing."""
        try:
            img = Image.open(image_path)
            img.thumbnail((max_size, max_size))
            temp_path = os.path.join(tempfile.gettempdir(), f"resized_{os.path.basename(image_path)}")
            img.save(temp_path)
            return temp_path
        except Exception as e:
            logging.error(f"Image resize failed: {e}")
            raise

    def upload(self):
        """Upload and resize an image for display and analysis."""
        path = ctk.filedialog.askopenfilename(filetypes=[("Image Files", "*.jpg *.jpeg *.png")])
        if not path:
            return
        if os.path.getsize(path) > MAX_IMAGE_SIZE:
            self.status_bar.configure(text="Image too large (max 10MB)", text_color="red")
            return
        try:
            filename = f"{uuid.uuid4().hex}{os.path.splitext(path)[1]}"
            dest = os.path.join(UPLOAD_DIR, filename)
            shutil.copy(path, dest)
            resized_path = self.resize_image(dest)
            self.image_path = resized_path
            self.display_image(resized_path)
            self.status_bar.configure(text="Image uploaded and resized successfully", text_color="green")
            logging.info(f"Image uploaded: {resized_path}")
        except Exception as e:
            self.status_bar.configure(text=f"Upload failed: {str(e)}", text_color="red")
            logging.error(f"Image upload error: {e}")

    def display_image(self, path):
        """Display the resized image in the GUI."""
        try:
            img = Image.open(path)
            img.thumbnail((400, 400))
            ctk_img = ctk.CTkImage(light_image=img, size=img.size)
            self.image_label.configure(image=ctk_img)
            self.image_label.image = ctk_img
        except Exception as e:
            self.image_label.configure(text="Failed to display image")
            logging.error(f"Image display error: {e}")

    def analyze(self):
        """Analyze the uploaded image for skin and cancer detection."""
        if not self.image_path:
            self.status_bar.configure(text="Please upload an image first", text_color="red")
            return
        detector = SkinDetector()
        try:
            self.status_bar.configure(text="Analyzing...", text_color="blue")
            _, skin_ratio = detector.detect_skin(self.image_path)
            cancer_prob, cancer_type, prevalence, advice, risk_level, cancer_detected = detector.detect_cancer(self.image_path)
            self.analysis_data = {
                "skin_ratio": skin_ratio, "cancer_prob": cancer_prob, "cancer_type": cancer_type,
                "prevalence": prevalence, "advice": advice, "risk_level": risk_level,
                "cancer_detected": cancer_detected, "analysis_date": datetime.now().strftime('%Y-%m-%d %H:%M')
            }
            self.update_risk_indicator(risk_level, cancer_detected)
            self.status_bar.configure(text="Analysis complete", text_color="green")
            self.save_btn.configure(state="normal")
            result_text = f"""Skin Coverage: {skin_ratio:.1%}
Cancer Probability: {cancer_prob:.1%}
Cancer Detected: {'Yes' if cancer_detected else 'No'}
Detected Cancer Type: {cancer_type}
Prevalence: {prevalence}
Risk Level: {risk_level.title()}

{advice}"""
            self.results_content.delete("1.0", "end")
            self.results_content.insert("end", result_text)
            logging.info(f"Analysis completed for image: {self.image_path}")
        except Exception as e:
            self.status_bar.configure(text=f"Analysis error: {str(e)}", text_color="red")
            logging.error(f"Analysis failed: {e}")

    def save(self):
        """Save analysis results to the database."""
        if self.image_path and self.analysis_data:
            try:
                image_id = self.parent.db.insert_image(self.parent.current_user["user_id"], self.image_path)
                if image_id:
                    analysis_id = self.parent.db.insert_analysis(
                        image_id, self.analysis_data["skin_ratio"], self.analysis_data["cancer_prob"],
                        self.analysis_data["cancer_type"], self.analysis_data["advice"])
                    if analysis_id:
                        self.status_bar.configure(text="Analysis saved successfully", text_color="green")
                        logging.info(f"Analysis saved with ID: {analysis_id}")
                        return
                self.status_bar.configure(text="Failed to save analysis", text_color="red")
            except Exception as e:
                self.status_bar.configure(text=f"Save failed: {str(e)}", text_color="red")
                logging.error(f"Save failed: {e}")

    def export_pdf(self):
        """Export analysis as a PDF report."""
        if not self.image_path or not self.analysis_data:
            self.status_bar.configure(text="No analysis to export", text_color="red")
            return
        try:
            file_path = ctk.filedialog.asksaveasfilename(
                defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")],
                initialfile=f"Skin_Cancer_Detect_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
            if not file_path:
                return
            user_data = {
                "username": self.parent.current_user["username"], "user_id": self.parent.current_user["user_id"],
                "email": self.parent.current_user["email"],
                "registration_date": self.parent.db.get_user_registration_date(self.parent.current_user["user_id"])
            }
            analysis_data = {
                **self.analysis_data,
                "disclaimer": ("This report is computer-generated and must be reviewed by a qualified medical professional. "
                               "Diagnostic decisions should not be based solely on this automated analysis.")
            }
            with tempfile.TemporaryDirectory() as tmp_dir:
                temp_img_path = os.path.join(tmp_dir, "analysis_image.jpg")
                img = Image.open(self.image_path)
                img.save(temp_img_path, quality=95)
                pdf = MedicalReport()
                pdf.add_page()
                pdf.add_report_content(user_data, analysis_data, temp_img_path)
                pdf.output(file_path)
            self.status_bar.configure(text=f"Report exported to: {file_path}", text_color="green")
            webbrowser.open(file_path)
            logging.info(f"PDF exported: {file_path}")
        except Exception as e:
            self.status_bar.configure(text=f"Export failed: {str(e)}", text_color="red")
            logging.error(f"PDF export error: {e}")

    def logout(self):
        """Log out and return to login page."""
        self.parent.current_user = None
        self.parent.show_page("LoginPage")
        logging.info("User logged out.")

###############################################################################################################
# History Page                                                                                                #
# Displays past analyses with options to view or delete them.                                                #
###############################################################################################################
class HistoryPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="#2B2B2B")
        header.grid(row=0, column=0, sticky="nsew")
        try:
            icon_img = Image.open("icon.png")
            icon_img = icon_img.resize((40, 40), Image.LANCZOS)
            ctk_icon = ctk.CTkImage(light_image=icon_img, size=(40, 40))
            ctk.CTkLabel(header, image=ctk_icon, text="").pack(side="left", padx=10)
        except Exception as e:
            logging.error(f"Failed to load history icon: {e}")
        ctk.CTkButton(header, text="← Back to Dashboard", font=("Arial", 14),
                      command=lambda: self.parent.show_page("DashboardPage")).pack(side="left", padx=20)
        ctk.CTkLabel(header, text="Patient History", font=("Arial", 18, "bold")).pack(side="left", padx=20)

        # Main content
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=2)

        # History list
        history_frame = ctk.CTkScrollableFrame(main, label_text="Previous Analyses",
                                               label_font=("Arial", 16), corner_radius=15)
        history_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.history_frame = history_frame

        # Preview area
        preview_frame = ctk.CTkFrame(main, corner_radius=15)
        preview_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.preview_image = ctk.CTkLabel(preview_frame, text="Select analysis to view",
                                          font=("Arial", 14), corner_radius=10)
        self.preview_image.pack(expand=True, fill="both", padx=10, pady=10)
        self.preview_text = ctk.CTkTextbox(preview_frame, font=("Arial", 12), wrap="word")
        self.preview_text.pack(fill="both", expand=True, padx=10, pady=10)

        self.status_bar = ctk.CTkLabel(self, text="", anchor="w",
                                       font=("Arial", 12), text_color="gray")
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=5)
        self.load_history(self.history_frame)

    def load_history(self, parent_frame):
        """Load and display user’s past analyses."""
        for widget in parent_frame.winfo_children():
            widget.destroy()
        analyses = self.parent.db.get_user_analyses(self.parent.current_user["user_id"])
        for analysis in analyses:
            entry = ctk.CTkFrame(parent_frame, corner_radius=8)
            entry.pack(fill="x", pady=5)
            date_str = analysis[2].strftime("%d %b %Y")
            cancer_type = analysis[5] if analysis[5] else "Unknown"
            risk_level = "high" if analysis[4] >= 0.5 else "moderate" if analysis[4] >= 0.2 else "low"
            colors = {"high": "#DC3545", "moderate": "#FFC107", "low": "#28A745"}
            ctk.CTkLabel(entry, text=date_str, width=100,
                         font=("Arial", 12), fg_color=colors[risk_level],
                         corner_radius=6).pack(side="left", padx=5)
            text = f"{cancer_type} - Risk: {risk_level.title()} ({analysis[4]:.1%})"
            ctk.CTkButton(entry, text=text, width=200, anchor="w",
                          command=lambda a=analysis: self.show_analysis(a)).pack(side="left", padx=5)
            ctk.CTkButton(entry, text="✖", width=30, fg_color="transparent",
                          hover_color="#DC3545", command=lambda aid=analysis[0]: self.delete_analysis(aid)
                          ).pack(side="right", padx=5)

    def show_analysis(self, analysis):
        """Display details of a selected analysis."""
        try:
            img = Image.open(analysis[7])
            img.thumbnail((300, 300))
            ctk_img = ctk.CTkImage(light_image=img, size=img.size)
            self.preview_image.configure(image=ctk_img, text="")
            self.preview_image.image = ctk_img
        except Exception as e:
            self.preview_image.configure(image=None, text="Image unavailable")
            logging.error(f"Failed to load history image: {e}")
        text = f"Date: {analysis[2].strftime('%Y-%m-%d %H:%M')}\n"
        text += f"Skin Coverage: {analysis[3]:.1%}\n"
        text += f"Cancer Probability: {analysis[4]:.1%}\n"
        text += f"Detected Cancer Type: {analysis[5] if analysis[5] else 'N/A'}\n"
        text += f"Advice: {analysis[6] if analysis[6] else 'No advice available'}"
        self.preview_text.delete("1.0", "end")
        self.preview_text.insert("end", text)

    def delete_analysis(self, analysis_id):
        """Delete an analysis and refresh the list."""
        if self.parent.db.delete_analysis(analysis_id):
            self.load_history(self.history_frame)
            self.preview_image.configure(image=None, text="Select analysis to view")
            self.preview_text.delete("1.0", "end")
            self.status_bar.configure(text="Analysis deleted successfully", text_color="green")
            logging.info(f"Analysis {analysis_id} deleted.")
        else:
            self.preview_text.delete("1.0", "end")
            self.preview_text.insert("end", "Deletion failed")
            self.status_bar.configure(text="Deletion failed", text_color="red")
            logging.error(f"Failed to delete analysis {analysis_id}")

###############################################################################################################
# About Page                                                                                                  #
# Displays app and team information.                                                                         #
###############################################################################################################
class AboutPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        frame = ctk.CTkFrame(self, corner_radius=15)
        frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        ctk.CTkLabel(frame, text="Skin Cancer Detection Pro", font=("Arial", 24, "bold")).pack(pady=20)
        ctk.CTkLabel(frame, text="Version: 1.0.1", font=("Arial", 16)).pack(pady=5)

        dev_frame = ctk.CTkFrame(frame, fg_color="transparent")
        dev_frame.pack(pady=20)
        ctk.CTkLabel(dev_frame, text="Developed by: Your Name", font=("Arial", 16, "bold")).pack(anchor="w")
        try:
            dev_img = Image.open("developer.png")
            dev_img = dev_img.resize((100, 100), Image.LANCZOS)
            ctk_dev_img = ctk.CTkImage(light_image=dev_img, size=(100, 100))
            ctk.CTkLabel(dev_frame, image=ctk_dev_img, text="").pack(pady=10)
        except Exception as e:
            logging.error(f"Failed to load developer image: {e}")
            ctk.CTkLabel(dev_frame, text="Developer image unavailable", font=("Arial", 14)).pack(pady=10)

        team_frame = ctk.CTkFrame(frame, fg_color="transparent")
        team_frame.pack(pady=20)
        ctk.CTkLabel(team_frame, text="Team Members:", font=("Arial", 18, "bold")).pack(anchor="w")

        members = [
            ("Team Member 1", "./dev/me.png"),
            ("Team Member 2", "./dev/me.png"),
            ("Team Member 3", "./dev/me.png")
        ]
        for name, img_path in members:
            member_frame = ctk.CTkFrame(team_frame, fg_color="transparent")
            member_frame.pack(fill="x", pady=5)
            try:
                img = Image.open(img_path)
                img = img.resize((50, 50), Image.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, size=(50, 50))
                ctk.CTkLabel(member_frame, image=ctk_img, text="").pack(side="left", padx=10)
            except Exception as e:
                logging.error(f"Failed to load image for {name}: {e}")
                ctk.CTkLabel(member_frame, text="Image unavailable", font=("Arial", 14)).pack(side="left", padx=10)
            ctk.CTkLabel(member_frame, text=name, font=("Arial", 14)).pack(side="left")

        ctk.CTkButton(frame, text="Back to Dashboard", command=lambda: self.parent.show_page("DashboardPage"),
                      width=250).pack(pady=20)

###############################################################################################################
# Main Application Class                                                                                      #
# Manages the app window, page navigation, and cleanup.                                                      #
###############################################################################################################
class MedicalApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Skin Cancer Detection")
        self.geometry("1366x768")
        self.minsize(1200, 700)
        try:
            img = Image.open("icon.png")
            self.iconphoto(True, ImageTk.PhotoImage(img))
        except Exception as e:
            logging.error(f"Failed to set app icon: {e}")
        ctk.set_widget_scaling(1.1)
        ctk.set_window_scaling(1.1)

        self.db = Database()
        self.current_user = None
        self.pages = {
            "LoginPage": LoginPage,
            "RegistrationPage": RegistrationPage,
            "DashboardPage": DashboardPage,
            "HistoryPage": HistoryPage,
            "AboutPage": AboutPage
        }
        self.show_page("LoginPage")

    def show_page(self, page_name):
        """Switch between app pages."""
        if hasattr(self, "current_page"):
            self.current_page.destroy()
        self.current_page = self.pages[page_name](self)
        self.current_page.pack(expand=True, fill="both")

    def on_closing(self):
        """Clean up resources on app close."""
        self.db.close()
        self.destroy()
        logging.info("Application closed.")

if __name__ == "__main__":
    app = MedicalApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
