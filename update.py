#############################################################################################################
#                                       Skin Cancer Detection Pro                                           #
#                                       A Python GUI Application                                            #
#############################################################################################################


##############################################################################################################
# Import necessary libraries                                                                                 #
# This application uses customtkinter for the GUI, OpenCV for image processing,                              #
# NumPy for numerical operations, PIL for image handling, psycopg2 for PostgreSQL database interaction,      #
# passlib for password hashing, cryptography for encryption, and fpdf for PDF generation.                    #
# The application also uses webbrowser for opening files and logging for error tracking.                     #
# The config module contains database configuration and encryption key.                                      #       
# The application is designed to be user-friendly and secure, with features for user registration,           #
# login, image upload, analysis, and report generation.                                                      #
# The code is structured into classes for better organization and maintainability.                           #
# Import standard libraries                                                                                  #
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
#                Setup logging to keep track of what's happening in the app                                  #
#               This is useful for debugging and understanding the flow of the application.                  #
#              The log file will be created in the same directory as the script.                             #
#             The log level is set to INFO, which means it will capture all messages at this level and above.#
#            The log format includes the timestamp, log level, and message.                                  #
#           The log file will be named 'app.log'.                                                            #
#          The logging module is a standard Python library for logging messages.                             #
#         The logging configuration is set up to log messages to a file and the console.                     #
# ############################################################################################################ 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

#############################################################################################################
#                         Make sure the upload directory exists for storing images                          #
#                        This is where the uploaded images will be saved before processing.                 #
#                       The directory is created if it doesn't already exist.                               #
#                      The os module is used for interacting with the operating system.                     #
#############################################################################################################

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

#############################################################################################################
#                            Set up encryption for securing image paths in the database                     #
#                           The cryptography library is used for encryption and decryption.                 #
#                          The Fernet symmetric encryption is used for secure data storage.                 #
#                         The encryption key is stored in a separate config file for security.              #
#                        The key should be kept secret and not hard-coded in the application.               #
#                       The encryption key is generated using the cryptography library.                     #
#                      The key is used to create a Fernet object for encryption and decryption.             #
#############################################################################################################
CIPHER = Fernet(ENCRYPTION_KEY)

###############################################################################################################
#                                         Database Management                                                 #
#                                       This class handles all database interactions.                         #
#                                      It connects to the PostgreSQL database and manages tables.             #
#                                     It provides methods for user registration, image upload, and analysis.  #
#                                    The psycopg2 library is used for PostgreSQL database interaction.        #
#                                   The passlib library is used for password hashing and verification.        #
#                                  The cryptography library is used for encrypting image paths.               #
#                                 The logging module is used for error tracking and debugging.                #
###############################################################################################################
class Database:
##############################################################################################################
#       Manages all database interactions for the Skin Cancer Detection app.                                 #
#      This includes connecting to the database, creating tables, and performing CRUD operations.            #
#     The psycopg2 library is used for PostgreSQL database interaction.                                      #
##############################################################################################################                                
    
    def __init__(self):
    
    
##############################################################################################################
#                               Connect to the PostgreSQL database and set up tables.                        #
#                              The psycopg2 library is used for PostgreSQL database interaction.             #
#                             The connection parameters are stored in a separate config file for security.   #
#                            The connection is established using the psycopg2.connect() method.              #
#                           The connection parameters include the database name, user, password, and host.   #
##############################################################################################################

        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cur = self.conn.cursor()


###############################################################################################################
#                                        Update schema if needed                                              #
#                                      This includes adding new columns to existing tables.                   #
###############################################################################################################       
        self.migrate_schema()  
##############################################################################################################
#                                        Create tables if they don’t exist.                                   #
###############################################################################################################
        self.create_tables()   

###############################################################################################################
#                       Update the database schema by adding new columns if they’re missing.                  #
###############################################################################################################
    def migrate_schema(self):
        try:

###############################################################################################################
#                    Add columns to the analyses table if they don’t already exist                            #
###############################################################################################################
            self.cur.execute("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS cancer_probability FLOAT")
            self.cur.execute("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS advice TEXT")
            self.cur.execute("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS cancer_type VARCHAR(50)")
            self.conn.commit()
            logging.info("Schema migration completed successfully.")
        except psycopg2.Error as e:
            logging.error(f"Schema migration failed: {e}")
            self.conn.rollback()

    def create_tables(self):

###############################################################################################################
#                       Create the required tables in the database if they don’t exist.                       #
###############################################################################################################
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
###############################################################################################################
#                       Remove an analysis entry from the database.                                           #
###############################################################################################################

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
        """Add a new user to the database."""
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

################################################################################################################
#                               Fetch user details by their username.                                          #
################################################################################################################

        query = "SELECT user_id, username, password_hash, email FROM users WHERE username = %s"
        try:
            self.cur.execute(query, (username,))
            return self.cur.fetchone()
        except psycopg2.Error as e:
            logging.error(f"User retrieval failed: {e}")
            return None

    def insert_image(self, user_id, image_path):

################################################################################################################
#                       Store an image path in the database, encrypted for security.                           #
################################################################################################################

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

################################################################################################################
#                  Save analysis results linked to an image.                                                   #
################################################################################################################
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
        """Retrieve all analyses for a given user, decrypting image paths."""
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
        """Get the user’s registration date for reporting."""
        query = "SELECT registration_date FROM users WHERE user_id = %s"
        try:
            self.cur.execute(query, (user_id,))
            result = self.cur.fetchone()
            return result[0].strftime('%Y-%m-%d') if result else "N/A"
        except psycopg2.Error as e:
            logging.error(f"Failed to get registration date: {e}")
            return "N/A"

    def close(self):
        """Safely close the database connection."""
        self.cur.close()
        self.conn.close()

# --- Skin Detection Logic ---
class SkinDetector:
    """Handles skin detection and cancer simulation in images."""
    
    def detect_skin(self, image_path):
        """Identify skin areas in an image using HSV color space."""
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError("Couldn’t load the image file.")
        # Convert to HSV for better skin detection
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lower_skin = np.array([0, 20, 70], dtype=np.uint8)
        upper_skin = np.array([20, 255, 255], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower_skin, upper_skin)
        skin_pixels = cv2.countNonZero(mask)
        total_pixels = image.shape[0] * image.shape[1]
        skin_image = cv2.bitwise_and(image, image, mask=mask)
        return skin_image, skin_pixels / total_pixels

    def detect_cancer(self, image_path):
        """Simulate cancer detection based on grayscale intensity."""
        image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError("Failed to load image for cancer detection.")
        avg_intensity = np.mean(image)
        probability = min(max((avg_intensity - 100) / 155, 0), 1)  # Normalize to 0-1
        cancer_detected = probability >= 0.3  # Threshold for detection

        # Classify cancer type based on intensity (simplified simulation)
        if avg_intensity <= 100:
            cancer_type = "Basal Cell Carcinoma"
            prevalence = "~80% of skin cancers"
            advice = "Basal Cell Carcinoma detected. Common but less severe. Consult a dermatologist for removal options."
            risk_level = "low"
        elif avg_intensity <= 150:
            cancer_type = "Squamous Cell Carcinoma"
            prevalence = "~16% of skin cancers"
            advice = "Squamous Cell Carcinoma detected. Moderate risk. See a dermatologist soon for a possible biopsy."
            risk_level = "moderate"
        elif avg_intensity <= 200:
            cancer_type = "Melanoma"
            prevalence = "~4% of skin cancers"
            advice = "Melanoma detected. High risk. Urgently consult an oncologist within 48 hours."
            risk_level = "high"
        else:
            cancer_type = "Merkel Cell Carcinoma"
            prevalence = "<1% of skin cancers"
            advice = "Merkel Cell Carcinoma detected. Rare and aggressive. Seek immediate medical attention."
            risk_level = "high"

        if not cancer_detected:
            cancer_type = "No Cancer Detected"
            prevalence = "N/A"
            advice = "No signs of malignancy. Continue with annual skin checks."
            risk_level = "low"

        advice += "\n\nNote: This is an automated analysis. Please consult a dermatologist for a professional review."
        return probability, cancer_type, prevalence, advice, risk_level, cancer_detected

# --- PDF Report Generation ---
class MedicalReport(FPDF):
    """Generates a professional PDF report for skin cancer analysis."""
    
    def __init__(self, icon_path='icon.png'):
        super().__init__()
        self.icon_path = icon_path

    def header(self):
        """Add a header with an icon and timestamp to each page."""
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
        """Add page numbers to the footer."""
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def add_report_content(self, user_data, analysis_data, image_path):
        """Fill the report with patient info, image, and analysis results."""
        # Patient Info Section
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Patient Information', 0, 1)
        self.set_font('Arial', '', 12)
        self.cell(0, 10, f'Name: {user_data["username"]}', 0, 1)
        self.cell(0, 10, f'Patient ID: {user_data["user_id"]}', 0, 1)
        self.cell(0, 10, f'Email: {user_data["email"]}', 0, 1)
        self.cell(0, 10, f'Registration Date: {user_data["registration_date"]}', 0, 1)
        self.ln(10)

        # Clinical Image Section
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Clinical Image', 0, 1)
        try:
            self.image(image_path, x=10, w=180)
            self.ln(100)
        except Exception as e:
            self.set_font('Arial', 'I', 10)
            self.cell(0, 10, f'Image unavailable: {str(e)}', 0, 1)
            self.ln(10)

        # Diagnostic Findings Table
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

        # Recommendations Section
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

# --- GUI Setup ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# --- Login Page ---
class LoginPage(ctk.CTkFrame):
    """The login screen where users enter their credentials."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Create a centered frame for the login form
        frame = ctk.CTkFrame(self, corner_radius=15)
        frame.grid(row=0, column=0, padx=30, pady=30, sticky="nsew")
        
        ctk.CTkLabel(frame, text="Skin Cancer Detection Pro", font=("Arial", 18, "bold")).pack(pady=20, anchor="center")
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
        """Check login credentials and switch to the dashboard if valid."""
        username = self.username.get().strip()
        password = self.password.get()
        if not username or not password:
            self.error_label.configure(text="Please fill all fields")
            return
        user = self.parent.db.get_user_by_username(username)
        if user and bcrypt.verify(password, user[2]):
            self.parent.current_user = {"user_id": user[0], "username": user[1], "email": user[3]}
            self.parent.show_page("DashboardPage")
        else:
            self.error_label.configure(text="Invalid credentials")

# --- Registration Page ---
class RegistrationPage(ctk.CTkFrame):
    """Screen for new users to register an account."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        frame = ctk.CTkFrame(self, corner_radius=15)
        frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        
        ctk.CTkLabel(frame, text="Skin Cancer Detection Pro", font=("Arial", 18, "bold")).pack(pady=20, anchor="center")
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
        """Handle registration and redirect to login on success."""
        username = self.username.get().strip()
        email = self.email.get().strip()
        password = self.password.get()
        if not all([username, email, password]):
            self.status_label.configure(text="All fields required", text_color="red")
            return
        if "@" not in email or "." not in email:
            self.status_label.configure(text="Invalid email format", text_color="red")
            return
        hashed = bcrypt.hash(password)
        user_id = self.parent.db.insert_user(username, hashed, email)
        if user_id:
            self.status_label.configure(text="Registration successful!", text_color="green")
            self.after(2000, lambda: self.parent.show_page("LoginPage"))
        else:
            self.status_label.configure(text="Username or email already taken", text_color="red")

# --- Dashboard Page ---
class DashboardPage(ctk.CTkFrame):
    """Main interface for uploading images, analyzing, and managing reports."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.image_path = None
        self.analysis_data = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header with navigation
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

        # Image display area
        self.image_panel = ctk.CTkFrame(main, corner_radius=15)
        self.image_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.image_label = ctk.CTkLabel(self.image_panel, text="Upload Dermatology Image",
                                        font=("Arial", 14), fg_color="#1A1A1A", corner_radius=10)
        self.image_label.pack(expand=True, fill="both", padx=10, pady=10)

        # Control buttons
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

        # Results display
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

        # Status bar for feedback
        self.status_bar = ctk.CTkLabel(self, text="Ready", anchor="w",
                                       font=("Arial", 12), text_color="gray")
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=5)

    def update_risk_indicator(self, risk_level, cancer_detected):
        """Update the risk indicator based on analysis results."""
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

    def upload(self):
        """Let the user upload an image and display it."""
        path = ctk.filedialog.askopenfilename(filetypes=[("Image Files", "*.jpg *.jpeg *.png")])
        if not path:
            return
        if os.path.getsize(path) > MAX_IMAGE_SIZE:  # Check size limit (e.g., 10MB)
            self.status_bar.configure(text="Image too large (max 10MB)", text_color="red")
            return
        try:
            filename = f"{uuid.uuid4().hex}{os.path.splitext(path)[1]}"
            dest = os.path.join(UPLOAD_DIR, filename)
            shutil.copy(path, dest)
            self.image_path = dest
            self.display_image(dest)
            self.status_bar.configure(text="Image uploaded successfully", text_color="green")
        except Exception as e:
            self.status_bar.configure(text=f"Upload failed: {str(e)}", text_color="red")
            logging.error(f"Image upload error: {e}")

    def display_image(self, path):
        """Show the uploaded image in the GUI."""
        try:
            img = Image.open(path)
            img.thumbnail((400, 400))  # Resize to fit nicely
            ctk_img = ctk.CTkImage(light_image=img, size=img.size)
            self.image_label.configure(image=ctk_img)
            self.image_label.image = ctk_img  # Keep reference to avoid garbage collection
        except Exception as e:
            self.image_label.configure(text="Failed to display image")
            logging.error(f"Image display error: {e}")

    def analyze(self):
        """Run skin and cancer detection on the uploaded image."""
        if not self.image_path:
            self.status_bar.configure(text="Please upload an image first", text_color="red")
            return
        detector = SkinDetector()
        try:
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
        except Exception as e:
            self.status_bar.configure(text=f"Analysis error: {str(e)}", text_color="red")
            logging.error(f"Analysis failed: {e}")

    def save(self):
        """Save the analysis results to the database."""
        if self.image_path and self.analysis_data:
            try:
                image_id = self.parent.db.insert_image(self.parent.current_user["user_id"], self.image_path)
                if image_id:
                    analysis_id = self.parent.db.insert_analysis(
                        image_id, self.analysis_data["skin_ratio"], self.analysis_data["cancer_prob"],
                        self.analysis_data["cancer_type"], self.analysis_data["advice"])
                    if analysis_id:
                        self.status_bar.configure(text="Analysis saved successfully", text_color="green")
                        return
                self.status_bar.configure(text="Failed to save analysis", text_color="red")
            except Exception as e:
                logging.error(f"Save failed: {e}")
                self.status_bar.configure(text=f"Save failed: {str(e)}", text_color="red")

    def export_pdf(self):
        """Generate and save a PDF report of the analysis."""
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
            with tempfile.TemporaryDirectory() as tmp_dir:  # Use temp dir to avoid clutter
                temp_img_path = os.path.join(tmp_dir, "analysis_image.jpg")
                img = Image.open(self.image_path)
                img.save(temp_img_path, quality=95)
                pdf = MedicalReport()
                pdf.add_page()
                pdf.add_report_content(user_data, analysis_data, temp_img_path)
                pdf.output(file_path)
            self.status_bar.configure(text=f"Report exported to: {file_path}", text_color="green")
            webbrowser.open(file_path)  # Open the PDF for the user
        except Exception as e:
            self.status_bar.configure(text=f"Export failed: {str(e)}", text_color="red")
            logging.error(f"PDF export error: {e}")

    def logout(self):
        """Log out and return to the login page."""
        self.parent.current_user = None
        self.parent.show_page("LoginPage")

# --- History Page ---
class HistoryPage(ctk.CTkFrame):
    """Displays the user’s past analyses with options to view or delete."""
    
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

        # Main content split into list and preview
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=2)

        # Scrollable history list
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
        """Populate the history list with past analyses."""
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
        """Show details of a selected analysis in the preview area."""
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
        """Remove an analysis from the database and refresh the list."""
        if self.parent.db.delete_analysis(analysis_id):
            self.load_history(self.history_frame)
            self.preview_image.configure(image=None, text="Select analysis to view")
            self.preview_text.delete("1.0", "end")
            self.status_bar.configure(text="Analysis deleted successfully", text_color="green")
        else:
            self.preview_text.delete("1.0", "end")
            self.preview_text.insert("end", "Deletion failed")
            self.status_bar.configure(text="Deletion failed", text_color="red")

# --- About Page ---
class AboutPage(ctk.CTkFrame):
    """Displays information about the app and its team."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        frame = ctk.CTkFrame(self, corner_radius=15)
        frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        # App info
        ctk.CTkLabel(frame, text="Skin Cancer Detection Pro", font=("Arial", 24, "bold")).pack(pady=20)
        ctk.CTkLabel(frame, text="Version: 1.0.0", font=("Arial", 16)).pack(pady=5)

        # Developer info
        dev_frame = ctk.CTkFrame(frame, fg_color="transparent")
        dev_frame.pack(pady=20)
        ctk.CTkLabel(dev_frame, text="Developed by: Your Name", font=("Arial", 16, "bold")).pack(anchor="w")
        try:
            dev_img = Image.open("developer.png")  # Update with your image path
            dev_img = dev_img.resize((100, 100), Image.LANCZOS)
            ctk_dev_img = ctk.CTkImage(light_image=dev_img, size=(100, 100))
            ctk.CTkLabel(dev_frame, image=ctk_dev_img, text="").pack(pady=10)
        except Exception as e:
            logging.error(f"Failed to load developer image: {e}")
            ctk.CTkLabel(dev_frame, text="Developer image unavailable", font=("Arial", 14)).pack(pady=10)

        # Team members
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

# --- Main Application ---
class MedicalApp(ctk.CTk):
    """The main window and controller for the Skin Cancer Detection app."""
    
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
        """Switch between different pages in the app."""
        if hasattr(self, "current_page"):
            self.current_page.destroy()
        self.current_page = self.pages[page_name](self)
        self.current_page.pack(expand=True, fill="both")

    def on_closing(self):
        """Clean up when the app is closed."""
        self.db.close()
        self.destroy()

if __name__ == "__main__":
    app = MedicalApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()