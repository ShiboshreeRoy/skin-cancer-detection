# ![🩺](https://img.icons8.com/emoji/24/stethoscope-emoji.png) Skin Cancer Detection Pro

![Version](https://img.shields.io/badge/version-1.0.1-blue.svg)  
*A professional-grade medical imaging system for dermatological diagnostics with AI-powered malignancy analysis, HIPAA-compliant security, and enterprise features.*

---

## 📸 App Overview

# Login 
![App Screenshot](./demo/Login.png)

---
# Register  
![Register](./demo/Register.png)

--- 

# Dashbord 
![Dashbord](./demo/Dashbord.png)

---
# Upload Image 
![Upload Image](./demo/Upload_image.png)

---
# Analize Image
![Analize Image](./demo/Analize_image.png)

---

# History
![History](./demo/Histry_image.png)

---
# Report (PDF)
![Report Skin](./demo/Report_Skin.png)
---
![Skin Report](./demo/Skin_Report.png)

**Skin Cancer Detection Pro** is a robust clinical-grade solution designed for dermatologists and research facilities. It leverages advanced image processing and AI-driven diagnostics for efficient and accurate skin lesion analysis.

---

## 🚀 Key Features

### 🔐 Secure Patient Portal
- Role-based access (Doctors / Patients)
- AES-256 encrypted credential storage
- JWT-based session tokens with activity logging
- Two-Factor Authentication (2FA)

### 🧠 AI-Powered Image Analysis
- Multi-spectral image support
- Real-time lesion detection with segmentation overlays
- Malignancy probability heatmaps
- Longitudinal data comparison

### 📄 Clinical Reporting Tools
- Automated clinical PDF generation
- DICOM-compatible imaging workflows
- HL7 FHIR-ready integration
- EHR-ready data export

### 🏢 Enterprise & Compliance
- HIPAA / GDPR-ready architecture
- Immutable audit logs
- Encrypted cloud backups (S3 / GCS / Azure)
- Audit-ready database schema

---

## 💻 System Requirements

- **Python** 3.9+
- **PostgreSQL** 14+
- **OpenCV** 4.5+ with CUDA (GPU optional)
- 8GB RAM (16GB recommended)
- NVIDIA GPU for acceleration (optional but recommended)

---

## ⚙️ Installation Guide

### 1. Clone Repository
```bash
git clone https://github.com/shiboshreeroy/skin-cancer-detection.git
cd skin-cancer-detection
````

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up Database

```bash
sudo -u postgres createdb skin_analysis
sudo -u postgres psql skin_analysis -f schema.sql
```

### 4. Create Configuration

Create a file named `config.py`:

```python
from cryptography.fernet import Fernet

DB_CONFIG = {
    'dbname': 'skin_analysis',
    'user': 'medical_user',
    'password': 'securepass123',
    'host': 'localhost',
    'port': 5432
}

ENCRYPTION_KEY = Fernet.generate_key()
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
UPLOAD_DIR = '/var/medical_images'
```

### 5. Prepare Upload Directory

```bash
mkdir -p /var/medical_images
chmod 700 /var/medical_images
```

---

## 🩺 Clinical Workflow

1. **User Authentication**

   * Doctor login (full system access)
   * Patient registration (limited access)

2. **Image Upload**

   * Accepts JPG, PNG, or DICOM formats

3. **Automated Analysis**

   * Lesion segmentation
   * Malignancy risk estimation (AI-driven)
   * Visualization overlays

4. **Report Generation**

   * Auto-generate PDF/Docx reports
   * Save to EHR with audit trail

5. **Advanced Features**

   * Batch processing for studies
   * Cross-time lesion comparison
   * PACS integration (via API)
   * DICOM metadata parsing

---

## 🔐 Security Architecture

![Security Diagram](security.png)

### Data Encryption

* AES-256 encryption at rest
* TLS 1.3 encryption in transit
* Secure hardware-backed key storage

### Access Controls

* Role-based (RBAC) enforcement
* Multi-factor authentication
* JWT session tokens with auto-expiry

### Compliance Readiness

* HIPAA, GDPR, and ISO 27001 alignment
* Immutable audit trail
* Periodic penetration testing

---

## 🛠️ Development Stack

**Languages / Libraries**

* Python 3.9
* CustomTkinter (UI)
* OpenCV + CUDA (Image Processing)
* PostgreSQL
* Fernet (Cryptography)

**Medical Standards**

* DICOM Image Support
* HL7 FHIR Messaging
* SNOMED CT Coding
* HIPAA Compliance Toolkit

---

## 🤝 Contributing

We follow rigorous clinical software engineering protocols:

* Submit RFCs for major features
* HIPAA training certification required
* Protected branches for PHI-related work
* Contributions must include:

  * 95%+ test coverage
  * Security audit checklist
  * Clinical validation documentation

---

## 📜 License

Licensed under the **Medical Device Open Source Agreement (MD-OSA 2.0)**:

* Commercial deployments require FDA clearance
* Diagnostic algorithm patents protected
* No liability for unsupervised clinical decisions

---

> ⚠️ **Disclaimer**: This system is intended for **licensed medical professionals**. AI-driven risk assessments are **decision support tools** and must be verified by qualified clinicians.

```
