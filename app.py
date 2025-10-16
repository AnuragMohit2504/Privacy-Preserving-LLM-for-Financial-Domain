"""
app.py - Enhanced Flask Backend for FINGPT
Privacy-Preserving Financial LLM Assistant

Features:
✅ Secure authentication with flask-login
✅ File upload (CSV/PDF) with validation
✅ RESTful API endpoints
✅ Session management
✅ Enhanced error handling
"""

import os
import csv
import json
import logging
from datetime import datetime
from flask import (
    Flask, render_template, request, jsonify, 
    redirect, url_for, send_from_directory, flash
)
from werkzeug.utils import secure_filename
from flask_login import (
    LoginManager, UserMixin, login_user, 
    logout_user, login_required, current_user
)

# ==================== CONFIGURATION ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"csv", "pdf", "xlsx", "xls"}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("FINGPT_SECRET", "dev-secret-key-change-in-production")
app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=3600
)

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ==================== AUTHENTICATION ====================
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."

# Demo users (In production, use a proper database)
USERS = {
    "demo@fingpt.ai": {"password": "demo123", "name": "Demo User"},
    "test@fingpt.local": {"password": "password", "name": "Test User"}
}

class User(UserMixin):
    def __init__(self, email):
        self.id = email
        self.email = email
        self.name = USERS[email]["name"]

@login_manager.user_loader
def load_user(user_id):
    return User(user_id) if user_id in USERS else None

# ==================== UTILITY FUNCTIONS ====================
def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def timestamp() -> str:
    """Return UTC ISO timestamp"""
    return datetime.utcnow().isoformat() + "Z"

def json_success(data, message="Success"):
    """Standardized JSON success response"""
    return jsonify({"status": "success", "message": message, "data": data})

def json_error(msg: str, code: int = 400):
    """Standardized JSON error response"""
    return jsonify({"status": "error", "message": msg}), code

# ==================== PAGE ROUTES ====================
@app.route("/")
def root():
    """Root redirect"""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page and handler"""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        
        user = USERS.get(email)
        if user and user["password"] == password:
            login_user(User(email), remember=True)
            flash("✅ Welcome back! Login successful.", "success")
            logger.info(f"User logged in: {email}")
            return redirect(url_for("dashboard"))
        
        flash("❌ Invalid credentials. Please try again.", "danger")
        logger.warning(f"Failed login attempt for: {email}")
    
    return render_template("login.html", project_name="FINGPT")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Signup page and handler"""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        
        if not all([name, email, password]):
            flash("⚠️ Please fill in all required fields.", "warning")
            return redirect(url_for("signup"))
        
        if len(password) < 8:
            flash("⚠️ Password must be at least 8 characters long.", "warning")
            return redirect(url_for("signup"))
        
        if email in USERS:
            flash("⚠️ Email already registered. Please log in instead.", "warning")
            return redirect(url_for("login"))
        
        # Add new user
        USERS[email] = {"password": password, "name": name}
        flash("✅ Account created successfully! Please log in.", "success")
        logger.info(f"New user registered: {email}")
        return redirect(url_for("login"))
    
    return render_template("signup.html", project_name="FINGPT")

@app.route("/logout")
@login_required
def logout():
    """Logout handler"""
    email = current_user.email
    logout_user()
    flash("👋 You've been logged out successfully.", "info")
    logger.info(f"User logged out: {email}")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    """Main dashboard"""
    return render_template(
        "dashboard.html", 
        project_name="FINGPT", 
        user_name=current_user.name
    )

# ==================== API ENDPOINTS ====================
@app.route("/api/upload", methods=["POST"])
@login_required
def api_upload():
    """Handle file uploads"""
    try:
        file = request.files.get("file")
        if not file or file.filename == "":
            return json_error("No file provided", 400)
        
        if not allowed_file(file.filename):
            return json_error(
                f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}", 
                400
            )
        
        # Secure filename
        filename = secure_filename(file.filename)
        timestamp_prefix = int(datetime.utcnow().timestamp())
        safe_name = f"{current_user.id.replace('@', '_')}_{timestamp_prefix}_{filename}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
        
        # Save file
        file.save(filepath)
        logger.info(f"File uploaded: {safe_name} by {current_user.email}")
        
        # Determine file type and available actions
        ext = filename.rsplit(".", 1)[1].lower()
        actions = {
            "csv": {
                "visualization": True, 
                "analyses": ["Bank Statement", "Transaction Analysis", "Expense Report"]
            },
            "pdf": {
                "visualization": False, 
                "analyses": ["Payslip Analysis", "Document Extraction"]
            },
            "xlsx": {
                "visualization": True,
                "analyses": ["Spreadsheet Analysis", "Financial Report"]
            },
            "xls": {
                "visualization": True,
                "analyses": ["Spreadsheet Analysis", "Financial Report"]
            }
        }
        
        return jsonify({
            "status": "success",
            "message": "File uploaded successfully",
            "data": {
                "uploaded_by": current_user.email,
                "original_filename": filename,
                "saved_filename": safe_name,
                "file_size": os.path.getsize(filepath),
                "file_type": ext,
                "timestamp": timestamp(),
                "actions": actions.get(ext, {})
            }
        })
    
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return json_error(f"Upload failed: {str(e)}", 500)

@app.route("/api/preview", methods=["GET"])
@login_required
def api_preview():
    """Preview CSV file contents"""
    try:
        filename = request.args.get("filename")
        rows_limit = int(request.args.get("rows", 10))
        
        if not filename:
            return json_error("Filename parameter required", 400)
        
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        
        if not os.path.exists(filepath):
            return json_error("File not found", 404)
        
        if not filename.endswith(".csv"):
            return json_error("Preview only available for CSV files", 400)
        
        # Read CSV
        with open(filepath, newline="", encoding="utf-8", errors="ignore") as fh:
            reader = csv.reader(fh)
            header = next(reader, [])
            rows = [row for _, row in zip(range(rows_limit), reader)]
        
        return jsonify({
            "status": "success",
            "data": {
                "columns": header,
                "rows": rows,
                "total_rows": rows_limit,
                "filename": filename
            }
        })
    
    except Exception as e:
        logger.error(f"Preview error: {str(e)}")
        return json_error(f"Preview failed: {str(e)}", 500)

@app.route("/api/vizdata", methods=["GET"])
@login_required
def api_vizdata():
    """Generate sample visualization data"""
    filename = request.args.get("filename")
    
    # Sample financial data
    sample_data = {
        "type": "financial_summary",
        "title": "Monthly Financial Overview",
        "periods": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        "series": [
            {
                "name": "Income",
                "values": [45000, 47500, 44000, 50000, 52000, 48000],
                "color": "#10b981"
            },
            {
                "name": "Expenses",
                "values": [32000, 30500, 35000, 33000, 34500, 36000],
                "color": "#ef4444"
            },
            {
                "name": "Savings",
                "values": [13000, 17000, 9000, 17000, 17500, 12000],
                "color": "#3b82f6"
            }
        ],
        "summary": {
            "total_income": 286500,
            "total_expenses": 201000,
            "total_savings": 85500,
            "savings_rate": 29.8
        }
    }
    
    return jsonify({
        "status": "success",
        "data": sample_data,
        "generated_at": timestamp()
    })

@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    """Handle chat messages"""
    try:
        payload = request.get_json() or {}
        message = (payload.get("message") or "").strip()
        filename = payload.get("filename")
        
        if not message:
            return json_error("Message cannot be empty", 400)
        
        # Process message (placeholder - integrate LLM here)
        reply = process_message(message, filename)
        
        return jsonify({
            "status": "success",
            "data": {
                "reply": reply,
                "timestamp": timestamp(),
                "context": {"filename": filename} if filename else {}
            }
        })
    
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return json_error(f"Chat processing failed: {str(e)}", 500)

def process_message(message: str, filename: str = None) -> str:
    """Process chat message and generate reply"""
    msg_lower = message.lower()
    
    # Intent detection (simple keyword matching - replace with NLP/LLM)
    if any(word in msg_lower for word in ["balance", "summary", "total"]):
        return "📊 I can help you analyze your financial balance. Your current data shows healthy financial activity with consistent savings patterns."
    
    elif any(word in msg_lower for word in ["expense", "spending", "cost"]):
        return "💸 Based on your uploaded data, your major expense categories are: Housing (35%), Food (20%), Transportation (15%), and Others (30%). Would you like a detailed breakdown?"
    
    elif any(word in msg_lower for word in ["income", "salary", "earning"]):
        return "💰 Your income analysis shows steady growth over the past months. Average monthly income: ₹48,500. Keep up the great work!"
    
    elif any(word in msg_lower for word in ["save", "saving", "invest"]):
        return "🎯 Your savings rate is approximately 30% - that's excellent! Consider diversifying into mutual funds or fixed deposits for better returns."
    
    elif any(word in msg_lower for word in ["visual", "chart", "graph"]):
        return "📈 I can generate visualizations for your data. Click 'Visualization Dashboard' to see interactive charts of your financial trends."
    
    elif filename and any(word in msg_lower for word in ["analyze", "analysis", "report"]):
        return f"🔍 I'm analyzing `{filename}` for you. This document contains financial transactions that I can break down by category, time period, or vendor. What specific insights are you looking for?"
    
    elif any(word in msg_lower for word in ["help", "what can you do", "capabilities"]):
        return """🤖 I'm FINGPT, your AI financial assistant! I can help you with:
        
• 📊 Analyze bank statements & transactions
• 💰 Review payslips & income
• 📈 Create visualizations & reports  
• 💡 Provide financial insights
• 🔒 All your data stays private & secure

Upload a file or ask me anything about your finances!"""
    
    else:
        return f"🤔 I understand you're asking about: '{message}'. I'm analyzing your financial data to provide insights. Could you be more specific about what you'd like to know?"

# ==================== ERROR HANDLERS ====================
@app.errorhandler(413)
def too_large(e):
    return json_error("File too large. Maximum size is 16MB.", 413)

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return json_error("API endpoint not found", 404)
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_error(e):
    logger.exception("Internal server error")
    return json_error("Internal server error occurred", 500)

# ==================== DEVELOPMENT SERVER ====================
if __name__ == "__main__":
    logger.info("Starting FINGPT server...")
    logger.info(f"Upload folder: {UPLOAD_FOLDER}")
    app.run(debug=True, port=5000, host="127.0.0.1")