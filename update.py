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


##################################################################################
#                                    Setup logging
#################################################################################
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


##################################################################################
#                           Ensure upload directory exists
##################################################################################


if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

##################################################################################
#                           Encryption setup
##################################################################################

CIPHER = Fernet(ENCRYPTION_KEY)

##################################################################################
#                Define script and assets directories
##################################################################################


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, "assets")


##################################################################################
#                           Database Management
##################################################################################


class Database:

##################################################################################
#       Manages database interactions for the app.
##################################################################################
    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cur = self.conn.cursor()
        self.migrate_schema()
        self.create_tables()

    def migrate_schema(self):

##################################################################################
#    Update database schema with new columns
##################################################################################

        try:
            self.cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS appearance_mode VARCHAR(10) DEFAULT 'dark'")
            self.cur.execute("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS cancer_probability FLOAT")
            self.cur.execute("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS advice TEXT")
            self.cur.execute("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS cancer_type VARCHAR(50)")
            self.conn.commit()
            logging.info("Schema migration completed.")
        except psycopg2.Error as e:
            logging.error(f"Schema migration failed: {e}")
            self.conn.rollback()

    def create_tables(self):

##################################################################################
#       Create necessary tables.
##################################################################################

        table_queries = [
            """CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                appearance_mode VARCHAR(10) DEFAULT 'dark',
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


##################################################################################
#         Delete an analysis.
##################################################################################


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

##################################################################################        
#       Insert a new user.
##################################################################################

        query = """INSERT INTO users (username, password_hash, email, appearance_mode)
                   VALUES (%s, %s, %s, 'dark') RETURNING user_id"""
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

##################################################################################
#       Fetch user by username.
##################################################################################

        query = "SELECT user_id, username, password_hash, email, appearance_mode FROM users WHERE username = %s"
        try:
            self.cur.execute(query, (username,))
            return self.cur.fetchone()
        except psycopg2.Error as e:
            logging.error(f"User retrieval failed: {e}")
            return None

    def get_user_by_email(self, email):

##################################################################################
#          Fetch user by email.
##################################################################################

        query = "SELECT user_id FROM users WHERE email = %s"
        try:
            self.cur.execute(query, (email,))
            result = self.cur.fetchone()
            return result[0] if result else None
        except psycopg2.Error as e:
            logging.error(f"Failed to get user by email: {e}")
            return None

    def update_user(self, user_id, username, email):

##################################################################################
#           Update user information.
##################################################################################

        query = "UPDATE users SET username = %s, email = %s WHERE user_id = %s"
        try:
            self.cur.execute(query, (username, email, user_id))
            self.conn.commit()
            return True
        except psycopg2.Error as e:
            logging.error(f"Failed to update user: {e}")
            self.conn.rollback()
            return False

    def update_appearance_mode(self, user_id, mode):

##################################################################################
#        Update user's appearance mode.
##################################################################################


        query = "UPDATE users SET appearance_mode = %s WHERE user_id = %s"
        try:
            self.cur.execute(query, (mode, user_id))
            self.conn.commit()
        except psycopg2.Error as e:
            logging.error(f"Failed to update appearance mode: {e}")
            self.conn.rollback()

    def insert_image(self, user_id, image_path):

##################################################################################
#        Insert an image with encrypted path.
##################################################################################


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

##################################################################################
#       Insert analysis results. 
##################################################################################


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

##################################################################################
#           Retrieve user's analyses with decrypted paths.
##################################################################################


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
                except Exception:
                    decrypted_path = "Decryption error"
                analyses.append((*analysis[:7], decrypted_path))
            return analyses
        except psycopg2.Error as e:
            logging.error(f"Failed to retrieve analyses: {e}")
            return []

    def get_user_registration_date(self, user_id):

##################################################################################
#        Get user's registration date
##################################################################################



        query = "SELECT registration_date FROM users WHERE user_id = %s"
        try:
            self.cur.execute(query, (user_id,))
            result = self.cur.fetchone()
            return result[0].strftime('%Y-%m-%d') if result else "N/A"
        except psycopg2.Error as e:
            logging.error(f"Failed to get registration date: {e}")
            return "N/A"

    def close(self):

##################################################################################
#           Close database connection
##################################################################################

        self.cur.close()
        self.conn.close()


##################################################################################
#           Skin Detection Logic
##################################################################################

class SkinDetector:


##################################################################################
#      Handles skin and cancer detection
##################################################################################


    def detect_skin(self, image_path):
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError("Couldn’t load image.")
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lower_skin = np.array([0, 20, 70], dtype=np.uint8)
        upper_skin = np.array([20, 255, 255], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower_skin, upper_skin)
        skin_pixels = cv2.countNonZero(mask)
        total_pixels = image.shape[0] * image.shape[1]
        skin_image = cv2.bitwise_and(image, image, mask=mask)
        return skin_image, skin_pixels / total_pixels

    def detect_cancer(self, image_path):
        image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError("Failed to load image.")
        avg_intensity = np.mean(image)
        probability = min(max((avg_intensity - 100) / 155, 0), 1)
        cancer_detected = probability >= 0.3
        if avg_intensity <= 100:
            cancer_type = "Basal Cell Carcinoma"
            advice = "Basal Cell Carcinoma detected. Consult a dermatologist."
            risk_level = "low"
        elif avg_intensity <= 150:
            cancer_type = "Squamous Cell Carcinoma"
            advice = "Squamous Cell Carcinoma detected. See a dermatologist soon."
            risk_level = "moderate"
        elif avg_intensity <= 200:
            cancer_type = "Melanoma"
            advice = "Melanoma detected. Urgently consult an oncologist."
            risk_level = "high"
        else:
            cancer_type = "Merkel Cell Carcinoma"
            advice = "Merkel Cell Carcinoma detected. Seek immediate attention."
            risk_level = "high"
        if not cancer_detected:
            cancer_type = "No Cancer Detected"
            advice = "No malignancy detected. Continue annual checks."
            risk_level = "low"
        advice += "\n\nNote: Consult a professional for accurate diagnosis."
        return probability, cancer_type, advice, risk_level, cancer_detected


##################################################################################
#      PDF Report Generation
##################################################################################


class MedicalReport(FPDF):

##################################################################################
#      Generates PDF reports
##################################################################################


    def __init__(self, icon_path=os.path.join(ASSETS_DIR, "icon.png")):
        super().__init__()
        self.icon_path = icon_path

    def header(self):
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
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def add_report_content(self, user_data, analysis_data, image_path):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Patient Information', 0, 1)
        self.set_font('Arial', '', 12)
        self.cell(0, 10, f'Name: {user_data["username"]}', 0, 1)
        self.cell(0, 10, f'Patient ID: {user_data["user_id"]}', 0, 1)
        self.cell(0, 10, f'Email: {user_data["email"]}', 0, 1)
        self.cell(0, 10, f'Registration Date: {user_data["registration_date"]}', 0, 1)
        self.ln(10)
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Clinical Image', 0, 1)
        try:
            self.image(image_path, x=10, w=180)
            self.ln(100)
        except Exception as e:
            self.set_font('Arial', 'I', 10)
            self.cell(0, 10, f'Image unavailable: {str(e)}', 0, 1)
            self.ln(10)
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
            ('Risk Classification', analysis_data["risk_level"].title()),
            ('Analysis Date', analysis_data["analysis_date"])
        ]
        for param, value in metrics:
            self.cell(95, 10, param, 1)
            self.cell(95, 10, value, 1, 1)
        self.ln(10)
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Clinical Recommendations', 0, 1)
        self.set_font('Arial', '', 12)
        self.multi_cell(0, 8, analysis_data["advice"])
        self.ln(5)
        self.ln(10)
        self.set_font('Arial', 'I', 8)
        self.multi_cell(0, 5, analysis_data["disclaimer"])


##################################################################################
#        GUI Setup
##################################################################################


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

##################################################################################
#         Login Page
##################################################################################


class LoginPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        frame = ctk.CTkFrame(self, corner_radius=15, fg_color="#1F2A44")
        frame.grid(row=0, column=0, padx=30, pady=30, sticky="nsew")
        ctk.CTkLabel(frame, text="Skin Cancer Detection Pro", font=("Arial", 18, "bold")).pack(pady=20)
        ctk.CTkLabel(frame, text="Patient Login", font=("Arial", 24, "bold")).pack(pady=20)
        self.username = ctk.CTkEntry(frame, placeholder_text="Username", width=250, height=50)
        self.username.pack(pady=10)
        self.password = ctk.CTkEntry(frame, placeholder_text="Password", show="*", width=250,height=50)
        self.password.pack(pady=10)
        ctk.CTkButton(frame, text="Login", command=self.login, width=250,height=50).pack(pady=10)
        ctk.CTkButton(frame, text="Register", command=lambda: self.parent.show_page("RegistrationPage"),
                      width=250,height=50, fg_color="transparent", border_width=2).pack(pady=10)
        self.error_label = ctk.CTkLabel(frame, text="", text_color="red")
        self.error_label.pack()

    def login(self):
        username = self.username.get().strip()
        password = self.password.get()
        if not username or not password:
            self.error_label.configure(text="Please fill all fields")
            return
        user = self.parent.db.get_user_by_username(username)
        if user and bcrypt.verify(password, user[2]):
            self.parent.current_user = {"user_id": user[0], "username": user[1], "email": user[3], "appearance_mode": user[4]}
            ctk.set_appearance_mode(user[4])
            self.parent.show_page("DashboardPage")
        else:
            self.error_label.configure(text="Invalid credentials")


##################################################################################
#      Registration Page
##################################################################################


class RegistrationPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        frame = ctk.CTkFrame(self, corner_radius=15, fg_color="#1F2A44")
        frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        ctk.CTkLabel(frame, text="Skin Cancer Detection Pro", font=("Arial", 18, "bold")).pack(pady=20)
        ctk.CTkLabel(frame, text="New Patient Registration", font=("Arial", 24, "bold")).pack(pady=20)
        self.username = ctk.CTkEntry(frame, placeholder_text="Username", width=250,height=50)
        self.username.pack(pady=10)
        self.email = ctk.CTkEntry(frame, placeholder_text="Email", width=250,height=50)
        self.email.pack(pady=10)
        self.password = ctk.CTkEntry(frame, placeholder_text="Password", show="*", width=250,height=50)
        self.password.pack(pady=10)
        ctk.CTkButton(frame, text="Register", command=self.register,width=250,height=50).pack(pady=10)
        ctk.CTkButton(frame, text="Back to Login", command=lambda: self.parent.show_page("LoginPage"),
                      width=250,height=50, fg_color="transparent", border_width=2).pack(pady=10)
        self.status_label = ctk.CTkLabel(frame, text="", text_color="green")
        self.status_label.pack()

    def register(self):
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
            self.status_label.configure(text="Username or email taken", text_color="red")


##################################################################################
#    Profile Page
##################################################################################


class ProfilePage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        frame = ctk.CTkFrame(self, corner_radius=15, fg_color="#1F2A44")
        frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        ctk.CTkLabel(frame, text="Patient Profile", font=("Arial", 24, "bold")).pack(pady=20)
        self.username_label = ctk.CTkLabel(frame, text=f"Username: {self.parent.current_user['username']}", font=("Arial", 16))
        self.username_label.pack(pady=5)
        self.username_entry = ctk.CTkEntry(frame, width=250)
        self.username_entry.insert(0, self.parent.current_user['username'])
        self.username_entry.pack(pady=5)
        self.username_entry.pack_forget()
        self.email_label = ctk.CTkLabel(frame, text=f"Email: {self.parent.current_user['email']}", font=("Arial", 16))
        self.email_label.pack(pady=5)
        self.email_entry = ctk.CTkEntry(frame, width=250)
        self.email_entry.insert(0, self.parent.current_user['email'])
        self.email_entry.pack(pady=5)
        self.email_entry.pack_forget()
        self.edit_button = ctk.CTkButton(frame, text="Edit", command=self.toggle_edit, width=250)
        self.edit_button.pack(pady=20)
        self.status_label = ctk.CTkLabel(frame, text="", font=("Arial", 14))
        self.status_label.pack(pady=10)
        ctk.CTkButton(frame, text="Back to Dashboard", command=lambda: self.parent.show_page("DashboardPage"), width=250).pack(pady=10)

    def toggle_edit(self):
        if self.edit_button.cget("text") == "Edit":
            self.username_label.pack_forget()
            self.email_label.pack_forget()
            self.username_entry.pack(pady=5)
            self.email_entry.pack(pady=5)
            self.edit_button.configure(text="Save")
        else:
            new_username = self.username_entry.get().strip()
            new_email = self.email_entry.get().strip()
            if not new_username or not new_email:
                self.status_label.configure(text="All fields required", text_color="red")
                return
            if "@" not in new_email or "." not in new_email:
                self.status_label.configure(text="Invalid email format", text_color="red")
                return
            if new_username != self.parent.current_user['username'] and self.parent.db.get_user_by_username(new_username):
                self.status_label.configure(text="Username already taken", text_color="red")
                return
            if new_email != self.parent.current_user['email'] and self.parent.db.get_user_by_email(new_email):
                self.status_label.configure(text="Email already taken", text_color="red")
                return
            success = self.parent.db.update_user(self.parent.current_user['user_id'], new_username, new_email)
            if success:
                self.parent.current_user['username'] = new_username
                self.parent.current_user['email'] = new_email
                self.status_label.configure(text="Profile updated", text_color="green")
                self.username_label.configure(text=f"Username: {new_username}")
                self.email_label.configure(text=f"Email: {new_email}")
                self.username_entry.pack_forget()
                self.email_entry.pack_forget()
                self.username_label.pack(pady=5)
                self.email_label.pack(pady=5)
                self.edit_button.configure(text="Edit")
            else:
                self.status_label.configure(text="Update failed", text_color="red")


##################################################################################
#    Dashboard Page
##################################################################################


class DashboardPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.image_path = None
        self.analysis_data = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)


##################################################################################
#         Header
##################################################################################



        header = ctk.CTkFrame(self, height=30, corner_radius=0, fg_color="#2B2B2B")
        header.grid(row=0, column=0, sticky="nsew")
        try:
            icon_img = Image.open(os.path.join(ASSETS_DIR, "icon.png"))
            icon_img = icon_img.resize((40, 40), Image.LANCZOS)
            ctk_icon = ctk.CTkImage(light_image=icon_img, size=(40, 40))
            ctk.CTkLabel(header, image=ctk_icon, text="").pack(side="left", padx=10)
        except Exception as e:
            logging.error(f"Failed to load header icon: {e}")
        ctk.CTkLabel(header, text=f"Patient: {self.parent.current_user['username']}", font=("Arial", 16, "bold")).pack(side="left", padx=20)
        self.theme_var = ctk.StringVar(value=self.parent.current_user["appearance_mode"])
        self.theme_switch = ctk.CTkSwitch(header, text="Dark Mode", variable=self.theme_var, onvalue="dark", offvalue="light", command=self.toggle_theme)
        self.theme_switch.pack(side="right", padx=10)
        nav_frame = ctk.CTkFrame(header, fg_color="transparent")
        nav_frame.pack(side="right", padx=40)
        ctk.CTkButton(nav_frame, text="Profile", command=lambda: self.parent.show_page("ProfilePage")).pack(side="left", padx=15)
        ctk.CTkButton(nav_frame, text="History", command=lambda: self.parent.show_page("HistoryPage")).pack(side="left", padx=15)
        ctk.CTkButton(nav_frame, text="Resources", command=lambda: self.parent.show_page("ResourcesPage")).pack(side="left", padx=15)
        ctk.CTkButton(nav_frame, text="About", command=lambda: self.parent.show_page("AboutPage")).pack(side="left", padx=15)
        ctk.CTkButton(nav_frame, text="Logout", fg_color="#3B3B3B", command=self.logout).pack(side="left", padx=15)

##################################################################################
#     Main layout
##################################################################################


        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        main.grid_columnconfigure(0, weight=2)
        main.grid_columnconfigure(1, weight=1)
        self.image_panel = ctk.CTkFrame(main, corner_radius=15)
        self.image_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.image_label = ctk.CTkLabel(self.image_panel, text="Upload Dermatology Image", font=("Arial", 14), fg_color="#1A1A1A", corner_radius=10)
        self.image_label.pack(expand=True, fill="both", padx=10, pady=10)
        control_panel = ctk.CTkFrame(main, corner_radius=15)
        control_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        try:
            upload_icon = ctk.CTkImage(light_image=Image.open(os.path.join(ASSETS_DIR, "upload.png")), size=(20, 20))
        except Exception as e:
            logging.error(f"Failed to load upload icon: {e}")
            upload_icon = None
        ctk.CTkButton(control_panel, image=upload_icon, text="Upload Image", height=40, font=("Arial", 14), command=self.upload, compound="left").pack(fill="x", pady=5)
        try:
            analyze_icon = ctk.CTkImage(light_image=Image.open(os.path.join(ASSETS_DIR, "analyze.png")), size=(20, 20))
        except Exception as e:
            logging.error(f"Failed to load analyze icon: {e}")
            analyze_icon = None
        ctk.CTkButton(control_panel, image=analyze_icon, text="Analyze", height=40, font=("Arial", 14), command=self.analyze, compound="left").pack(fill="x", pady=5)
        try:
            save_icon = ctk.CTkImage(light_image=Image.open(os.path.join(ASSETS_DIR, "save.png")), size=(20, 20))
        except Exception as e:
            logging.error(f"Failed to load save icon: {e}")
            save_icon = None
        self.save_btn = ctk.CTkButton(control_panel, image=save_icon, text="Save Report", height=40, font=("Arial", 14), state="disabled", command=self.save, compound="left")
        self.save_btn.pack(fill="x", pady=5)
        try:
            export_icon = ctk.CTkImage(light_image=Image.open(os.path.join(ASSETS_DIR, "export.png")), size=(20, 20))
        except Exception as e:
            logging.error(f"Failed to load export icon: {e}")
            export_icon = None
        ctk.CTkButton(control_panel, image=export_icon, text="Export PDF", height=40, font=("Arial", 14), command=self.export_pdf, compound="left").pack(fill="x", pady=5)
        self.results_frame = ctk.CTkFrame(main, height=200, corner_radius=15)
        self.results_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        self.risk_indicator = ctk.CTkLabel(self.results_frame, text="RISK LEVEL", font=("Arial", 24, "bold"), width=200, height=200, corner_radius=100)
        self.risk_indicator.pack(side="left", padx=20, pady=20)
        results_text = ctk.CTkFrame(self.results_frame, fg_color="transparent")
        results_text.pack(side="left", fill="both", expand=True)
        self.results_header = ctk.CTkLabel(results_text, text="Analysis Results", font=("Arial", 18, "bold"))
        self.results_header.pack(anchor="w", pady=5)
        self.results_content = ctk.CTkTextbox(results_text, font=("Arial", 14), wrap="word")
        self.results_content.pack(expand=True, fill="both")
        self.status_bar = ctk.CTkLabel(self, text="Ready", anchor="w", font=("Arial", 12), text_color="gray")
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=5)

    def toggle_theme(self):
        mode = self.theme_var.get()
        ctk.set_appearance_mode(mode)
        self.parent.db.update_appearance_mode(self.parent.current_user["user_id"], mode)
        self.parent.current_user["appearance_mode"] = mode

    def update_risk_indicator(self, risk_level, cancer_detected):
        colors = {"low": ("#2AA876", "LOW RISK"), "moderate": ("#FFC107", "MODERATE RISK"), "high": ("#DC3545", "HIGH RISK")}
        color, text = colors[risk_level]
        if cancer_detected:
            text += " - DETECTED"
        self.risk_indicator.configure(text=text, fg_color=color)
        self.results_header.configure(text_color=color)

    def upload(self):
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
            self.image_path = dest
            self.display_image(dest)
            self.status_bar.configure(text="Image uploaded", text_color="green")
        except Exception as e:
            self.status_bar.configure(text=f"Upload failed: {str(e)}", text_color="red")

    def display_image(self, path):
        try:
            img = Image.open(path)
            img.thumbnail((400, 400))
            ctk_img = ctk.CTkImage(light_image=img, size=img.size)
            self.image_label.configure(image=ctk_img, text="")
            self.image_label.image = ctk_img
        except Exception as e:
            self.image_label.configure(text="Failed to display image")

    def analyze(self):
        if not self.image_path:
            self.status_bar.configure(text="Upload an image first", text_color="red")
            return
        detector = SkinDetector()
        try:
            _, skin_ratio = detector.detect_skin(self.image_path)
            cancer_prob, cancer_type, advice, risk_level, cancer_detected = detector.detect_cancer(self.image_path)
            self.analysis_data = {
                "skin_ratio": skin_ratio, "cancer_prob": cancer_prob, "cancer_type": cancer_type,
                "advice": advice, "risk_level": risk_level, "cancer_detected": cancer_detected,
                "analysis_date": datetime.now().strftime('%Y-%m-%d %H:%M')
            }
            self.update_risk_indicator(risk_level, cancer_detected)
            self.status_bar.configure(text="Analysis complete", text_color="green")
            self.save_btn.configure(state="normal")
            result_text = f"""Skin Coverage: {skin_ratio:.1%}
Cancer Probability: {cancer_prob:.1%}
Cancer Detected: {'Yes' if cancer_detected else 'No'}
Detected Cancer Type: {cancer_type}
Risk Level: {risk_level.title()}

{advice}"""
            self.results_content.delete("1.0", "end")
            self.results_content.insert("end", result_text)
        except Exception as e:
            self.status_bar.configure(text=f"Analysis error: {str(e)}", text_color="red")

    def save(self):
        if self.image_path and self.analysis_data:
            try:
                image_id = self.parent.db.insert_image(self.parent.current_user["user_id"], self.image_path)
                if image_id:
                    analysis_id = self.parent.db.insert_analysis(
                        image_id, self.analysis_data["skin_ratio"], self.analysis_data["cancer_prob"],
                        self.analysis_data["cancer_type"], self.analysis_data["advice"])
                    if analysis_id:
                        self.status_bar.configure(text="Analysis saved", text_color="green")
                        return
                self.status_bar.configure(text="Failed to save", text_color="red")
            except Exception as e:
                self.status_bar.configure(text=f"Save failed: {str(e)}", text_color="red")

    def export_pdf(self):
        if not self.image_path or not self.analysis_data:
            self.status_bar.configure(text="No analysis to export", text_color="red")
            return
        try:
            file_path = ctk.filedialog.asksaveasfilename(
                defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")],
                initialfile=f"Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
            if not file_path:
                return
            user_data = {
                "username": self.parent.current_user["username"], "user_id": self.parent.current_user["user_id"],
                "email": self.parent.current_user["email"],
                "registration_date": self.parent.db.get_user_registration_date(self.parent.current_user["user_id"])
            }
            analysis_data = {
                **self.analysis_data,
                "disclaimer": "This is an automated analysis. Consult a medical professional."
            }
            with tempfile.TemporaryDirectory() as tmp_dir:
                temp_img_path = os.path.join(tmp_dir, "analysis_image.jpg")
                img = Image.open(self.image_path)
                img.save(temp_img_path, quality=95)
                pdf = MedicalReport(icon_path=os.path.join(ASSETS_DIR, "icon.png"))
                pdf.add_page()
                pdf.add_report_content(user_data, analysis_data, temp_img_path)
                pdf.output(file_path)
            self.status_bar.configure(text=f"Exported to: {file_path}", text_color="green")
            webbrowser.open(file_path)
        except Exception as e:
            self.status_bar.configure(text=f"Export failed: {str(e)}", text_color="red")

    def logout(self):
        self.parent.current_user = None
        self.parent.show_page("LoginPage")


##################################################################################
#    History Page
##################################################################################

class HistoryPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.selected_analyses = set()
        self.analysis_vars = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="#2B2B2B")
        header.grid(row=0, column=0, sticky="nsew")
        try:
            icon_img = Image.open(os.path.join(ASSETS_DIR, "icon.png"))
            icon_img = icon_img.resize((40, 40), Image.LANCZOS)
            ctk_icon = ctk.CTkImage(light_image=icon_img, size=(40, 40))
            ctk.CTkLabel(header, image=ctk_icon, text="").pack(side="left", padx=10)
        except Exception as e:
            logging.error(f"Failed to load history icon: {e}")
        ctk.CTkButton(header, text="← Back to Dashboard", font=("Arial", 14), command=lambda: self.parent.show_page("DashboardPage")).pack(side="left", padx=20)
        ctk.CTkLabel(header, text="Patient History", font=("Arial", 18, "bold")).pack(side="left", padx=20)
        control_frame = ctk.CTkFrame(self, height=50, fg_color="transparent")
        control_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        self.compare_button = ctk.CTkButton(control_frame, text="Compare Selected", command=self.compare_analyses)
        self.compare_button.pack(side="left", padx=10)
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=2, column=0, sticky="nsew", padx=20, pady=20)
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=2)
        self.history_frame = ctk.CTkScrollableFrame(main, label_text="Previous Analyses", label_font=("Arial", 16), corner_radius=15)
        self.history_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.preview_frame = ctk.CTkFrame(main, corner_radius=15)
        self.preview_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.preview_image = ctk.CTkLabel(self.preview_frame, text="Select analysis to view", font=("Arial", 14), corner_radius=10)
        self.preview_image.pack(expand=True, fill="both", padx=10, pady=10)
        self.preview_text = ctk.CTkTextbox(self.preview_frame, font=("Arial", 12), wrap="word")
        self.preview_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.analysis_frame1 = ctk.CTkFrame(self.preview_frame)
        self.analysis_frame1.pack(side="left", fill="both", expand=True, padx=5)
        self.analysis_frame1.pack_forget()
        self.analysis_image1 = ctk.CTkLabel(self.analysis_frame1, text="")
        self.analysis_image1.pack(expand=True, fill="both")
        self.analysis_text1 = ctk.CTkTextbox(self.analysis_frame1, font=("Arial", 12), wrap="word")
        self.analysis_text1.pack(fill="both", expand=True)
        self.analysis_frame2 = ctk.CTkFrame(self.preview_frame)
        self.analysis_frame2.pack(side="left", fill="both", expand=True, padx=5)
        self.analysis_frame2.pack_forget()
        self.analysis_image2 = ctk.CTkLabel(self.analysis_frame2, text="")
        self.analysis_image2.pack(expand=True, fill="both")
        self.analysis_text2 = ctk.CTkTextbox(self.analysis_frame2, font=("Arial", 12), wrap="word")
        self.analysis_text2.pack(fill="both", expand=True)
        self.back_button = ctk.CTkButton(self.preview_frame, text="Back", command=self.back_to_list)
        self.back_button.pack(pady=10)
        self.back_button.pack_forget()
        self.status_bar = ctk.CTkLabel(self, text="", anchor="w", font=("Arial", 12), text_color="gray")
        self.status_bar.grid(row=3, column=0, sticky="ew", padx=20, pady=5)
        self.load_history()

    def load_history(self):
        for widget in self.history_frame.winfo_children():
            widget.destroy()
        analyses = self.parent.db.get_user_analyses(self.parent.current_user["user_id"])
        for analysis in analyses:
            entry = ctk.CTkFrame(self.history_frame, corner_radius=8)
            entry.pack(fill="x", pady=5)
            var = ctk.IntVar(value=0)
            self.analysis_vars[analysis[0]] = var
            cb = ctk.CTkCheckBox(entry, text="", variable=var, command=lambda aid=analysis[0]: self.update_selection(aid))
            cb.pack(side="left", padx=5)
            date_str = analysis[2].strftime("%d %b %Y")
            cancer_type = analysis[5] if analysis[5] else "Unknown"
            risk_level = "high" if analysis[4] >= 0.5 else "moderate" if analysis[4] >= 0.2 else "low"
            colors = {"high": "#DC3545", "moderate": "#FFC107", "low": "#28A745"}
            ctk.CTkLabel(entry, text=date_str, width=100, font=("Arial", 12), fg_color=colors[risk_level], corner_radius=6).pack(side="left", padx=5)
            text = f"{cancer_type} - Risk: {risk_level.title()} ({analysis[4]:.1%})"
            ctk.CTkButton(entry, text=text, width=200, anchor="w", command=lambda a=analysis: self.show_analysis(a)).pack(side="left", padx=5)
            ctk.CTkButton(entry, text="✖", width=30, fg_color="transparent", hover_color="#DC3545", command=lambda aid=analysis[0]: self.delete_analysis(aid)).pack(side="right", padx=5)

    def update_selection(self, aid):
        if self.analysis_vars[aid].get() == 1:
            self.selected_analyses.add(aid)
        else:
            self.selected_analyses.discard(aid)

    def compare_analyses(self):
        if len(self.selected_analyses) != 2:
            self.status_bar.configure(text="Select exactly two analyses", text_color="red")
            return
        analyses = [a for a in self.parent.db.get_user_analyses(self.parent.current_user["user_id"]) if a[0] in self.selected_analyses]
        if len(analyses) != 2:
            self.status_bar.configure(text="Selected analyses not found", text_color="red")
            return
        self.preview_image.pack_forget()
        self.preview_text.pack_forget()
        for i, analysis in enumerate(analyses):
            try:
                img = Image.open(analysis[7])
                img.thumbnail((200, 200))
                ctk_img = ctk.CTkImage(light_image=img, size=img.size)
                if i == 0:
                    self.analysis_image1.configure(image=ctk_img, text="")
                    self.analysis_image1.image = ctk_img
                else:
                    self.analysis_image2.configure(image=ctk_img, text="")
                    self.analysis_image2.image = ctk_img
            except Exception:
                if i == 0:
                    self.analysis_image1.configure(image=None, text="Image unavailable")
                else:
                    self.analysis_image2.configure(image=None, text="Image unavailable")
            text = f"Date: {analysis[2].strftime('%Y-%m-%d %H:%M')}\n"
            text += f"Skin Coverage: {analysis[3]:.1%}\n"
            text += f"Cancer Probability: {analysis[4]:.1%}\n"
            text += f"Detected Cancer Type: {analysis[5] if analysis[5] else 'N/A'}\n"
            text += f"Advice: {analysis[6] if analysis[6] else 'No advice'}"
            if i == 0:
                self.analysis_text1.delete("1.0", "end")
                self.analysis_text1.insert("end", text)
            else:
                self.analysis_text2.delete("1.0", "end")
                self.analysis_text2.insert("end", text)
        self.analysis_frame1.pack(side="left", fill="both", expand=True, padx=5)
        self.analysis_frame2.pack(side="left", fill="both", expand=True, padx=5)
        self.back_button.pack(pady=10)

    def back_to_list(self):
        for aid in self.analysis_vars:
            self.analysis_vars[aid].set(0)
        self.selected_analyses.clear()
        self.analysis_frame1.pack_forget()
        self.analysis_frame2.pack_forget()
        self.preview_image.pack(expand=True, fill="both", padx=10, pady=10)
        self.preview_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.preview_image.configure(image=None, text="Select analysis to view")
        self.preview_text.delete("1.0", "end")
        self.back_button.pack_forget()

    def show_analysis(self, analysis):
        try:
            img = Image.open(analysis[7])
            img.thumbnail((300, 300))
            ctk_img = ctk.CTkImage(light_image=img, size=img.size)
            self.preview_image.configure(image=ctk_img, text="")
            self.preview_image.image = ctk_img
        except Exception:
            self.preview_image.configure(image=None, text="Image unavailable")
        text = f"Date: {analysis[2].strftime('%Y-%m-%d %H:%M')}\n"
        text += f"Skin Coverage: {analysis[3]:.1%}\n"
        text += f"Cancer Probability: {analysis[4]:.1%}\n"
        text += f"Detected Cancer Type: {analysis[5] if analysis[5] else 'N/A'}\n"
        text += f"Advice: {analysis[6] if analysis[6] else 'No advice'}"
        self.preview_text.delete("1.0", "end")
        self.preview_text.insert("end", text)

    def delete_analysis(self, analysis_id):
        if self.parent.db.delete_analysis(analysis_id):
            self.load_history()
            self.preview_image.configure(image=None, text="Select analysis to view")
            self.preview_text.delete("1.0", "end")
            self.status_bar.configure(text="Analysis deleted", text_color="green")
        else:
            self.status_bar.configure(text="Deletion failed", text_color="red")


##################################################################################
#   Resources Page
##################################################################################


class ResourcesPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        frame = ctk.CTkFrame(self, corner_radius=15, fg_color="#1F2A44")
        frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        ctk.CTkLabel(frame, text="Educational Resources", font=("Arial", 24, "bold")).pack(pady=20)
        ctk.CTkLabel(frame, text="What is Skin Cancer?", font=("Arial", 18, "bold")).pack(anchor="w", pady=10)
        ctk.CTkLabel(frame, text="Skin cancer is the abnormal growth of skin cells, often caused by UV radiation.", wraplength=600, justify="left").pack(anchor="w")
        link1 = ctk.CTkLabel(frame, text="Learn more", text_color="blue", cursor="hand2")
        link1.pack(anchor="w", pady=5)
        link1.bind("<Button-1>", lambda e: webbrowser.open("https://www.cancer.org/cancer/skin-cancer.html"))
        ctk.CTkLabel(frame, text="Types of Skin Cancer", font=("Arial", 18, "bold")).pack(anchor="w", pady=10)
        ctk.CTkLabel(frame, text="Includes Basal Cell Carcinoma, Squamous Cell Carcinoma, and Melanoma.", wraplength=600, justify="left").pack(anchor="w")
        link2 = ctk.CTkLabel(frame, text="More info", text_color="blue", cursor="hand2")
        link2.pack(anchor="w", pady=5)
        link2.bind("<Button-1>", lambda e: webbrowser.open("https://www.skincancer.org/skin-cancer-information/"))
        ctk.CTkLabel(frame, text="Prevention and Treatment", font=("Arial", 18, "bold")).pack(anchor="w", pady=10)
        ctk.CTkLabel(frame, text="Use sunscreen, wear protective clothing, and consult professionals for treatment.", wraplength=600, justify="left").pack(anchor="w")
        link3 = ctk.CTkLabel(frame, text="Resources", text_color="blue", cursor="hand2")
        link3.pack(anchor="w", pady=5)
        link3.bind("<Button-1>", lambda e: webbrowser.open("https://www.aad.org/public/diseases/skin-cancer"))
        ctk.CTkButton(frame, text="Back to Dashboard", command=lambda: self.parent.show_page("DashboardPage"), width=250).pack(pady=20)


##################################################################################
#    About Page
##################################################################################


class AboutPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        frame = ctk.CTkFrame(self, corner_radius=15, fg_color="#1F2A44")
        frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        ctk.CTkLabel(frame, text="Skin Cancer Detection Pro", font=("Arial", 24, "bold")).pack(pady=20)
        ctk.CTkLabel(frame, text="Version: 1.0.0", font=("Arial", 16)).pack(pady=5)
        dev_frame = ctk.CTkFrame(frame, fg_color="transparent")
        dev_frame.pack(pady=20)
        ctk.CTkLabel(dev_frame, text="Developed by: Your Name", font=("Arial", 16, "bold")).pack(anchor="w")
        try:
            dev_img = Image.open(os.path.join(ASSETS_DIR, "developer.png"))
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
            ("Team Member 1", os.path.join(ASSETS_DIR, "member1.png")),
            ("Team Member 2", os.path.join(ASSETS_DIR, "member2.png")),
            ("Team Member 3", os.path.join(ASSETS_DIR, "member3.png"))
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
                logging.error(f"Failed to load team member image {img_path}: {e}")
                ctk.CTkLabel(member_frame, text="Image unavailable", font=("Arial", 14)).pack(side="left", padx=10)
            ctk.CTkLabel(member_frame, text=name, font=("Arial", 14)).pack(side="left")
        ctk.CTkButton(frame, text="Back to Dashboard", command=lambda: self.parent.show_page("DashboardPage"), width=250).pack(pady=20)



##################################################################################
#   Main Application
##################################################################################


class MedicalApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Skin Cancer Detection")
        self.geometry("1366x768")
        self.minsize(1200, 700)
        try:
            img = Image.open(os.path.join(ASSETS_DIR, "icon.png"))
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
            "ProfilePage": ProfilePage,
            "DashboardPage": DashboardPage,
            "HistoryPage": HistoryPage,
            "ResourcesPage": ResourcesPage,
            "AboutPage": AboutPage
        }
        self.show_page("LoginPage")

    def show_page(self, page_name):
        if hasattr(self, "current_page"):
            self.current_page.destroy()
        self.current_page = self.pages[page_name](self)
        self.current_page.pack(expand=True, fill="both")

    def on_closing(self):
        self.db.close()
        self.destroy()

if __name__ == "__main__":
    app = MedicalApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
