from werkzeug.security import generate_password_hash, check_password_hash
import os
import logging
import requests
import pandas as pd
import PyPDF2
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

from database import (
    get_user, create_user, log_file_upload, log_chat_message, 
    log_analysis_result, insert_audit_log, get_user_files, 
    get_chat_history, update_privacy_budget, init_pool, close_pool,
    get_training_rounds
)
from feature_extractor import extract_features, serialize_features
from fl_bridge import (
    check_fl_status, submit_features_for_training, get_model_insights,
    get_training_status, trigger_fl_round
)
import requests
import fitz  # PyMuPDF
import pdfplumber
import re



BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"csv", "pdf", "xlsx", "xls"}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:latest"

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

app.config["OLLAMA_URL"] = "http://localhost:11434/api/generate"
app.config["MODEL_NAME"] = "llama3.2:latest"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."

def clean_numbers(arr):
    cleaned = []
    for x in arr:
        try:
            x = str(x).replace(",", "").strip()
            cleaned.append(float(x))
        except:
            cleaned.append(0.0)
    return cleaned


def extract_pdf_text(filepath):
    doc = fitz.open(filepath)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def initialize_he_context():
    try:
        r = requests.post(
            "http://127.0.0.1:9000/init_context",
            json={
                "poly_modulus_degree": 8192,
                "coeff_mod_bit_sizes": [60, 40, 40, 60]
            },
            timeout=5
        )

        if r.status_code == 200:
            logger.info("✅ HE context initialized successfully")
        else:
            logger.warning(f"⚠️ HE init failed: {r.status_code} - {r.text}")

    except requests.exceptions.ConnectionError:
        logger.error("❌ HE server not reachable. Make sure it's running on port 9000.")
    except Exception as e:
        logger.error(f"❌ HE initialization error: {str(e)}")

class User(UserMixin):
    def __init__(self, email, name):
        self.id = email
        self.email = email
        self.name = name

@login_manager.user_loader
def load_user(user_id):
    user = get_user(user_id)
    return User(user['email'], user['name']) if user else None

def query_ollama(prompt, system_prompt=None):
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 2000
            }
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            return result.get("response", "No response received from AI")
        else:
            logger.error(f"Ollama error: {response.status_code}")
            return "⚠️ AI service unavailable. Please ensure Ollama is running with 'ollama serve'."
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to Ollama")
        return "⚠️ Cannot connect to AI service. Please start Ollama: Run 'ollama serve' in a terminal."
    except requests.exceptions.Timeout:
        logger.error("Ollama timeout")
        return "⚠️ AI service timed out. Please try again."
    except Exception as e:
        logger.error(f"Ollama query error: {str(e)}")
        return f"⚠️ AI analysis error: {str(e)}"

def extract_text_from_pdf(filepath):
    try:
        with open(filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
    except Exception as e:
        logger.error(f"PDF extraction error: {str(e)}")
        return None

def analyze_document(filepath, file_type, analysis_type):
    try:
        if file_type == 'pdf':
            pdf_text = extract_text_from_pdf(filepath)
            if not pdf_text:
                return {"status": "error", "message": "Failed to extract text from PDF"}
            
            if len(pdf_text) > 4000:
                pdf_text = pdf_text[:4000] + "\n\n[... truncated ...]"
            
            data_preview = pdf_text
        elif file_type == 'csv':
            df = pd.read_csv(filepath)
            data_preview = df.head(50).to_string(index=False, max_colwidth=50)
        else:
            return {"status": "error", "message": "Unsupported file format"}
        
        if 'payslip' in analysis_type.lower() or 'salary' in analysis_type.lower():
            system_prompt = "You are an HR and payroll analyst AI. Analyze salary structures and deductions."
            user_prompt = f"""Analyze this payslip/salary document:

{data_preview}

Provide analysis on:
1. 💼 Employee & Company Details
2. 💰 Gross Salary Breakdown
3. 📉 Deductions
4. 💵 Net Pay
5. 📊 Salary Structure Analysis
6. 💡 Insights"""
        else:
            system_prompt = """
            STRICT: Never generate data not present in input.
            
            You are a professional financial analyst AI.

            IMPORTANT:
            Always respond in clean structured HTML format.

            Use:
            <h3>Section Title</h3>
            <ul><li>Points</li></ul>
            <b>for important values</b>

            Format response like:

            <h3>Account Summary</h3>
            <ul>
            <li>Balance: ₹...</li>
            <li>Total Transactions: ...</li>
            </ul>

            <h3>Spending Analysis</h3>
            <ul>
            <li>Food: ₹...</li>
            <li>Transport: ₹...</li>
            </ul>

            Keep it clean and UI-friendly.
            No markdown. Only HTML.
            """
            user_prompt = f"""Analyze this bank statement:

{data_preview}

Provide output in HTML format using:
<h3> for headings
<ul><li> for lists

Sections:
1. 📋 Account Summary
2. 💰 Financial Overview
3. 📊 Transaction Analysis
4. 🏷️ Spending Categories
5. 📈 Patterns & Trends
6. 💡 Insights & Recommendations"""
        
        ai_response = query_ollama(user_prompt, system_prompt)
        
        return {
            "status": "success",
            "ai_analysis": ai_response,
            "model_used": OLLAMA_MODEL
        }
    
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        return {"status": "error", "message": str(e)}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def root():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form["email"].lower()
        password = request.form["password"]

        user = get_user(email)

        if user and check_password_hash(user['password_hash'], password):
            login_user(User(user['email'], user['name']), remember=True)
            insert_audit_log("USER_LOGIN", f"User {email} logged in")
            flash("Login successful", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password", "danger")

    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"].lower()
        password = request.form["password"]

        if len(password) < 8:
            flash("Password must be at least 8 characters", "warning")
            return redirect(url_for("signup"))

        password_hash = generate_password_hash(password)

        try:
            create_user(email, name, password_hash)
            insert_audit_log("USER_SIGNUP", f"New user registered: {email}")
            flash("Account created! Please login.", "success")
            return redirect(url_for("login"))
        except:
            flash("Email already exists", "danger")

    return render_template("signup.html")

@app.route("/logout")
@login_required
def logout():
    email = current_user.email
    logout_user()
    insert_audit_log("USER_LOGOUT", f"User {email} logged out")
    flash("You've been logged out successfully.", "info")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    fl_status = check_fl_status()
    return render_template(
        "dashboard.html", 
        project_name="FINGPT", 
        user_name=current_user.name,
        fl_status=fl_status
    )

@app.route("/api/upload", methods=["POST"])
@login_required
def api_upload():
    try:
        file = request.files.get("file")
        if not file or file.filename == "":
            return jsonify({"status": "error", "message": "No file provided"}), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                "status": "error", 
                "message": f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            }), 400
        
        filename = secure_filename(file.filename)
        timestamp_prefix = int(datetime.utcnow().timestamp())
        safe_name = f"{current_user.id.replace('@', '').replace('.', '_')}_{timestamp_prefix}_{filename}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
        
        file.save(filepath)
        
        file_size = os.path.getsize(filepath)
        ext = filename.rsplit(".", 1)[1].lower()
        
        file_id = log_file_upload(
            current_user.email,
            safe_name,
            filename,
            ext,
            file_size,
            filepath
        )
        
        insert_audit_log("FILE_UPLOAD", f"User {current_user.email} uploaded {filename}")
        
        actions = {
            "csv": {
                "visualization": True, 
                "analyses": ["Bank Statement Analysis", "Transaction Analysis", "FL Training", "Visualization"]
            },
            "pdf": {
                "visualization": False, 
                "analyses": ["Bank Statement Analysis", "Payslip Analysis", "FL Training"]
            },
            "xlsx": {
                "visualization": True,
                "analyses": ["Spreadsheet Analysis", "FL Training", "Visualization"]
            }
        }
        
        response_data = {
            "status": "success",
            "message": "File uploaded successfully",
            "data": {
                "original_filename": filename,
                "saved_filename": safe_name,
                "file_id": file_id,
                "file_size": file_size,
                "file_type": ext,
                "uploaded_by": current_user.email,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "actions": actions.get(ext, {})
            }
        }
        
        return jsonify(response_data)
    
    except Exception as e:
        logger.error(f"Upload error: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    try:
        payload = request.get_json() or {}
        message = (payload.get("message") or "").strip()
        filename = payload.get("filename")
        file_id = payload.get("file_id")
        
        if not message:
            return jsonify({"status": "error", "message": "Message cannot be empty"}), 400
        
        log_chat_message(current_user.email, message, "user", file_id)
        
        msg_lower = message.lower()
        has_file = filename and os.path.exists(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        
        # ================================
        # 🔥 COMMON DATA PREVIEW (CRITICAL)
        # ================================

        data_preview = ""

        if has_file:
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file_ext = filename.rsplit(".", 1)[1].lower()

            try:
                if file_ext == "pdf":
                    data_preview = extract_text_from_pdf(filepath) or ""
                    data_preview = data_preview[:3000]  # limit size
                elif file_ext == "csv":
                    df = pd.read_csv(filepath)
                    data_preview = df.head(50).to_string(index=False)
            except Exception as e:
                logger.error(f"Data extraction error: {str(e)}")
                data_preview = ""
        # 🔥 INTENT DETECTION
        if "dashboard" in msg_lower:
            intent = "dashboard"
        elif "budget" in msg_lower:
            intent = "budget"
        elif "unusual" in msg_lower or "fraud" in msg_lower:
            intent = "anomaly"
        elif "analyze" in msg_lower:
            intent = "analysis"
        else:
            intent = "general"
        general_keywords = [
            'how', 'what', 'why', 'when', 'where', 'who',
            'create', 'plan', 'budget', 'advice', 'tips', 'help',
            'recommend', 'suggest', 'guide', 'explain', 'tell', 'find'
        ]
        is_general_question = any(keyword in msg_lower for keyword in general_keywords)
        
        if has_file and any(word in msg_lower for word in ['fl training', 'submit', 'federated', 'train model', 'training']):
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file_ext = filename.rsplit(".", 1)[1].lower()
            
            analysis_type = 'payslip' if 'payslip' in filename.lower() else 'bank'
            
            try:
                feature_vector, features_dict = extract_features(filepath, file_ext, analysis_type)
                fl_result = submit_features_for_training(feature_vector, features_dict)
                
                if fl_result.get("status") == "success":
                    update_privacy_budget(current_user.email, 0.5)
                    
                    reply = f"""<div style='background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(139, 92, 246, 0.1)); padding: 20px; border-radius: 12px; border: 1px solid rgba(59, 130, 246, 0.3);'>
<h3 style='color: #3b82f6; margin-bottom: 16px;'>🔐 Privacy-Preserving FL Training Initiated</h3>
<div style='display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 16px;'>
<div style='background: rgba(0,0,0,0.2); padding: 12px; border-radius: 8px;'>
<div style='font-size: 12px; color: #9ca3af; margin-bottom: 4px;'>Features Extracted</div>
<div style='font-size: 20px; font-weight: 700; color: #10b981;'>{len(feature_vector)} dimensions</div>
</div>
<div style='background: rgba(0,0,0,0.2); padding: 12px; border-radius: 8px;'>
<div style='font-size: 12px; color: #9ca3af; margin-bottom: 4px;'>Pending Features</div>
<div style='font-size: 20px; font-weight: 700; color: #f59e0b;'>{fl_result.get('total_pending', 0)}</div>
</div>
</div>
<div style='background: rgba(0,0,0,0.2); padding: 12px; border-radius: 8px; margin-bottom: 12px;'>
<div style='font-size: 13px;'><strong>Privacy Guarantee:</strong> Differential Privacy + Homomorphic Encryption</div>
<div style='font-size: 13px;'><strong>Status:</strong> {fl_result.get('message', 'Training queued')}</div>
</div>
<p style='font-size: 14px; color: #d1d5db;'>✅ Your financial data has been converted to encrypted features and submitted for federated learning. Original data never leaves your device!</p>
<div style='margin-top: 16px;'>
<button onclick='navigateToSection("fl-monitor")' style='padding: 10px 20px; background: linear-gradient(135deg, #3b82f6, #8b5cf6); color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600;'>View FL Monitor →</button>
</div>
</div>"""
                else:
                    reply = f"❌ FL Training failed: {fl_result.get('message', 'Unknown error')}"
            except Exception as e:
                logger.error(f"FL training error: {str(e)}")
                reply = f"❌ Failed to extract features: {str(e)}"
        
        elif has_file and any(word in msg_lower for word in ['analyze', 'analysis', 'bank', 'statement', 'payslip', 'salary', 'spending', 'expense']):
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file_ext = filename.rsplit(".", 1)[1].lower()
            
            analysis_type = 'payslip' if any(word in msg_lower for word in ['payslip', 'salary']) else 'bank statement'
            
            analysis_result = analyze_document(filepath, file_ext, analysis_type)
            
            if analysis_result["status"] == "success":
                file_type = "PDF" if file_ext == 'pdf' else "CSV"
                reply = f"""<div style='background: rgba(16, 185, 129, 0.1); padding: 20px; border-radius: 12px; border: 1px solid rgba(16, 185, 129, 0.3);'>
<h3 style='color: #10b981; margin-bottom: 12px;'>📊 {analysis_type.title()} Analysis</h3>
<div style='background: rgba(0,0,0,0.2); padding: 12px; border-radius: 8px; margin-bottom: 16px;'>
<strong>📄 File:</strong> {os.path.basename(filename)} ({file_type})<br>
<strong>🤖 AI Model:</strong> {analysis_result['model_used']}
</div>
<div style='line-height: 1.8; color: #e5e7eb;'>
{analysis_result['ai_analysis']}
</div>
</div>"""
                
                if file_id:
                    log_analysis_result(
                        file_id,
                        analysis_type,
                        {"ai_response": analysis_result['ai_analysis']}
                    )
            else:
                reply = f"❌ Analysis failed: {analysis_result.get('message', 'Unknown error')}"
        
        # ================================
        # 🔥 NEW INTENT ROUTING
        # ================================

        elif intent == "dashboard":
            # system_prompt = """
            # STRICT: Never generate data not present in input.
            
            # You are a financial dashboard generator AI.

            # STRICT RULES:
            # - Output ONLY HTML
            # - NO explanations
            # - NO notes
            # - NO JavaScript
            # - NO examples
            # - NO markdown
            # - NO placeholder text like $X
            # - NO instructions

            # ONLY generate final UI content.

            # FORMAT:

            # <h3>Financial Dashboard</h3>

            # <ul>
            # <li><b>Total Income:</b> ₹XXXX</li>
            # <li><b>Total Expenses:</b> ₹XXXX</li>
            # <li><b>Savings:</b> ₹XXXX</li>
            # </ul>

            # <h3>Expense Breakdown</h3>
            # <ul>
            # <li>Food: ₹XXXX</li>
            # <li>Transport: ₹XXXX</li>
            # <li>Shopping: ₹XXXX</li>
            # </ul>

            # <h3>Key Metrics</h3>
            # <ul>
            # <li>Average Monthly Spend: ₹XXXX</li>
            # <li>Savings Rate: XX%</li>
            # </ul>

            # <h3>Trends</h3>
            # <ul>
            # <li>Spending increasing/decreasing</li>
            # <li>Major expense category</li>
            # </ul>

            # IMPORTANT:
            # Keep it clean and readable.
            # """
            
            # # ================================
            # # 🔥 CALCULATE FINANCIAL METRICS
            # # ================================

            # # total_income = 0
            # # total_expense = 0

            # # for line in data_preview.split("\n"):
            # #     line_lower = line.lower()

            # #     if "credit" in line_lower or "deposit" in line_lower:
            # #         nums = [float(x.replace(",", "")) for x in line.split() if x.replace(",", "").replace(".", "").isdigit()]
            # #         if nums:
            # #             total_income += nums[-1]

            # #     if "debit" in line_lower or "withdraw" in line_lower:
            # #         nums = [float(x.replace(",", "")) for x in line.split() if x.replace(",", "").replace(".", "").isdigit()]
            # #         if nums:
            # #             total_expense += nums[-1]

            # # savings = total_income - total_expense

            # reply = query_ollama(
            #     f"""
            #     You are given financial transaction data:

            #     {data_preview}

            #     TASK:
            #     Extract and calculate:

            #     - Total Income (sum of credits/deposits)
            #     - Total Expenses (sum of debits/withdrawals)
            #     - Savings = Income - Expenses

            #     RULES:
            #     - ONLY use actual amounts from data
            #     - DO NOT use placeholders like XXXX
            #     - DO NOT skip calculations
            #     - If category missing → write "Not Available"
            #     - Ignore transaction IDs and references

            #     OUTPUT STRICTLY IN HTML:

            #     <h3>Financial Dashboard</h3>

            #     <ul>
            #     <li><b>Total Income:</b> ₹VALUE</li>
            #     <li><b>Total Expenses:</b> ₹VALUE</li>
            #     <li><b>Savings:</b> ₹VALUE</li>
            #     </ul>

            #     <h3>Expense Breakdown</h3>
            #     <ul>
            #     <li>Food: ₹VALUE</li>
            #     <li>Transport: ₹VALUE</li>
            #     <li>Shopping: ₹VALUE</li>
            #     </ul>

            #     <h3>Key Metrics</h3>
            #     <ul>
            #     <li>Average Monthly Spend: ₹VALUE</li>
            #     <li>Savings Rate: VALUE%</li>
            #     </ul>

            #     <h3>Trends</h3>
            #     <ul>
            #     <li>Describe spending trend</li>
            #     <li>Largest expense category</li>
            #     </ul>
            #     """,
            #     system_prompt
            # )
                        return jsonify({
                "status": "success",
                "data": {
                    "reply": "📊 Opening dashboard..."
                }
            })


        elif intent == "budget":
            system_prompt = """
            STRICT: Never generate data not present in input.
            
            You are a financial planning AI.

            STRICT RULES:
            - Output ONLY HTML
            - NO explanations
            - NO examples
            - NO placeholder values like $X
            - NO notes

            Generate a realistic budget plan.

            FORMAT:

            <h3>Budget Plan</h3>

            <h4>Income Allocation</h4>
            <ul>
            <li>Essential Expenses: ₹XXXX</li>
            <li>Savings: ₹XXXX</li>
            <li>Discretionary Spending: ₹XXXX</li>
            </ul>

            <h4>Essential Expenses</h4>
            <ul>
            <li>Rent: ₹XXXX</li>
            <li>Food: ₹XXXX</li>
            <li>Transport: ₹XXXX</li>
            </ul>

            <h4>Savings Strategy</h4>
            <ul>
            <li>Emergency Fund: ₹XXXX</li>
            <li>Investments: ₹XXXX</li>
            </ul>

            IMPORTANT:
            Keep output clean and structured.
            """

            reply = query_ollama(
                f"""
                Create a realistic budget plan using ONLY valid financial amounts from this data:

                {data_preview}

                IMPORTANT RULES:
                - Only treat values labeled as Amount, Debit, Credit, Balance as money
                - Ignore IDs, reference numbers, transaction numbers
                - Do NOT sum random numbers
                - Do NOT include transaction IDs in calculations

                If unsure, skip the value.

                """,
                system_prompt
            )


        elif intent == "anomaly":
            system_prompt = """
            STRICT: Never generate data not present in input.
            
            You are a fraud detection AI.

            Identify suspicious or unusual financial transactions.

            Respond ONLY in HTML:

            <h3>Suspicious Transactions</h3>
            <ul><li>...</li></ul>

            <h3>Risk Indicators</h3>
            <ul><li>...</li></ul>

            <h3>Recommendations</h3>
            <ul><li>...</li></ul>
            """

            reply = query_ollama(
                f"""
                Identify suspicious transactions ONLY from this dataset:

                {data_preview}

                RULES:
                - DO NOT create fake transactions
                - Only use real entries
                - If none found → say "No suspicious transactions found"
                """,
                system_prompt
            )
    
        elif is_general_question and not has_file:
            system_prompt = """
                STRICT: Never generate data not present in input.
            
                You are FINGPT Enterprise, an AI financial analytics assistant designed for
                businesses, finance teams, and auditors.
                
                Always respond in clean HTML format.

                Use:
                <h3> headings
                <ul><li> bullet points

                Keep responses structured and readable.

                Your role is to help organizations analyze financial documents such as:
                - bank statements
                - payroll reports
                - expense data
                - transaction logs

                Provide insights useful for:
                - financial risk detection
                - expense anomalies
                - compliance monitoring
                - operational financial insights

                Focus on business value, patterns, and decision support.
                Avoid personal budgeting advice.
                """
            
            reply = query_ollama(
                f"""
                User question: {message}

                Financial data:
                {data_preview}

                Answer ONLY using the provided data.
                """,
                system_prompt
            )
            
            if not reply.startswith("⚠️"):
                reply += "\n\n💡 <em>For personalized analysis based on your actual data, upload your bank statement or payslip using the 📎 button!</em>"
        
        elif has_file:
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file_ext = filename.rsplit(".", 1)[1].lower()
            
            if file_ext == 'csv':
                try:
                    df = pd.read_csv(filepath)
                    data_summary = f"File has {len(df)} rows and {len(df.columns)} columns: {', '.join(df.columns.tolist()[:5])}"
                except:
                    data_summary = "CSV file uploaded"
            else:
                data_summary = f"{file_ext.upper()} file uploaded"
            
            system_prompt = f"""You are FINGPT, analyzing the user's uploaded file: {filename}.
The file contains: {data_summary}

Provide helpful insights and answer questions about their financial data."""
            reply = query_ollama(message, system_prompt)
        
        else:
            system_prompt = "You are FINGPT, a helpful financial advisor AI assistant with privacy-preserving capabilities. Provide practical financial guidance."
            reply = query_ollama(message, system_prompt)
        
        log_chat_message(current_user.email, reply, "bot", file_id)
        
        return jsonify({
            "status": "success",
            "data": {
                "reply": reply,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        })
    
    except Exception as e:
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error", 
            "message": "An error occurred processing your message. Please try again."
        }), 500

@app.route("/api/fl_status", methods=["GET"])
@login_required
def api_fl_status():
    try:
        status = check_fl_status()
        training_status = get_training_status()
        
        combined_status = {
            **status,
            "training": training_status,
            "user_privacy_budget": get_user_privacy_budget(current_user.email)
        }
        
        return jsonify(combined_status)
    except Exception as e:
        logger.error(f"FL status error: {str(e)}")
        return jsonify({
            "status": "offline",
            "components": {},
            "stats": {"current_round": 0, "pending_features": 0, "active_clients": 0}
        })

@app.route("/api/training_logs", methods=["GET"])
@login_required
def api_training_logs():
    try:
        logs = get_training_rounds(limit=50)
        return jsonify([dict(log) for log in logs])
    except Exception as e:
        logger.error(f"Training logs error: {str(e)}")
        return jsonify([])

@app.route("/api/trigger_round", methods=["POST"])
@login_required
def api_trigger_round():
    try:
        result = trigger_fl_round()
        
        if result.get("status") == "success":
            insert_audit_log(
                "FL_ROUND_TRIGGERED",
                f"User {current_user.email} triggered round {result.get('round')}"
            )
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Trigger round error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/preview", methods=["GET"])
@login_required
def api_preview():
    try:
        filename = request.args.get("filename")
        rows_limit = int(request.args.get("rows", 10))
        
        if not filename:
            return jsonify({"status": "error", "message": "Filename required"}), 400
        
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        
        if not os.path.exists(filepath):
            return jsonify({"status": "error", "message": "File not found"}), 404
        
        if not filename.endswith(".csv"):
            return jsonify({"status": "error", "message": "Preview only available for CSV"}), 400
        
        df = pd.read_csv(filepath, nrows=rows_limit)
        
        return jsonify({
            "status": "ok",
            "columns": df.columns.tolist(),
            "rows": df.values.tolist(),
            "total_rows": len(df),
            "filename": filename
        })
    
    except Exception as e:
        logger.error(f"Preview error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

def classify_transaction_category(narration: str) -> str:
    """Classify transaction into categories based on narration/description"""
    narration_lower = narration.lower()
    
    category_keywords = {
        'Food & Dining': ['restaurant', 'food', 'swiggy', 'zomato', 'cafe', 'coffee', 'pizza', 'burger', 'meal', 'lunch', 'dinner', 'breakfast'],
        'Entertainment': ['movie', 'entertainment', 'netflix', 'amazon prime', 'hotstar', 'spotify', 'gaming', 'music', 'concert', 'cinema'],
        'Finance': ['emi', 'loan', 'credit card', 'insurance', 'mutual fund', 'investment', 'stock', 'bank transfer', 'wire'],
        'Shopping': ['amazon', 'flipkart', 'myntra', 'shopping', 'mall', 'store', 'retail', 'clothing', 'dress', 'shoes'],
        'Transportation': ['uber', 'ola', 'taxi', 'fuel', 'petrol', 'diesel', 'parking', 'transport', 'train', 'bus', 'flight'],
        'Utilities': ['electricity', 'water', 'internet', 'mobile', 'phone', 'bill', 'broadband', 'gas'],
        'Medical & Health': ['hospital', 'doctor', 'pharmacy', 'medical', 'health', 'dental', 'clinic', 'medicine'],
        'Rent & Housing': ['rent', 'mortgage', 'house', 'home', 'property'],
        'Groceries': ['grocery', 'supermarket', 'mart', 'blinkit', 'bigbasket', 'jiomart', 'vegetables', 'milk'],
        'Salary': ['salary', 'wage', 'income', 'credit', 'deposit']
    }
    
    for category, keywords in category_keywords.items():
        if any(keyword in narration_lower for keyword in keywords):
            return category
    
    return 'Other'

@app.route("/api/vizdata", methods=["GET"])
@login_required
def api_vizdata():
    filename = request.args.get("filename")
    
    if not filename:
        sample_data = {
            "type": "financial_summary",
            "title": "Monthly Financial Overview",
            "x": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
            "series": [
                {
                    "name": "Income",
                    "values": [45000, 47500, 44000, 50000, 52000, 48000]
                },
                {
                    "name": "Expenses",
                    "values": [32000, 30500, 35000, 33000, 34500, 36000]
                }
            ]
        }
        
        return jsonify({
            "status": "success",
            "payload": sample_data,
            "generated_at": datetime.utcnow().isoformat() + "Z"
        })
    
    try:
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        
        if not os.path.exists(filepath):
            return jsonify({"status": "error", "message": "File not found"}), 404
        
        # ===============================
        # FILE TYPE HANDLING
        # ===============================

        if filename.endswith(".csv"):
            df = pd.read_csv(filepath)

        elif filename.endswith(".pdf"):
            dates = []
            transactions = []  # Store with narration for categorization
            
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()

                    if not text:
                        continue

                    lines = text.split("\n")

                    for line in lines:
                        # Detect date line with narration
                        if re.match(r"\d{2}-[A-Za-z]{3}-\d{4}", line):
                            parts = line.split()
                            numbers = [p.replace(",", "") for p in parts]
                            
                            # Extract numbers and narration
                            nums = [float(p.replace("Rs.", "")) for p in numbers if re.match(r"^\d+(\.\d+)?$", p.replace("Rs.", ""))]
                            
                            if len(nums) >= 2:
                                date_str = parts[0]
                                # Extract narration (middle part between date and amounts)
                                narration_parts = [p for p in parts[1:-2] if not re.match(r"^\d+", p.replace(",", "").replace("Rs.", ""))]
                                narration = " ".join(narration_parts) if narration_parts else "Transaction"
                                
                                amt1 = nums[-2]
                                is_withdrawal = "UPI" in line or "ATM" in line or "Debit" in line
                                
                                transactions.append({
                                    'date': date_str,
                                    'narration': narration,
                                    'amount': amt1,
                                    'is_withdrawal': is_withdrawal
                                })

            if not transactions:
                return jsonify({"status": "error", "message": "No transactions found"}), 400

            # Convert dates to datetime for grouping
            for tx in transactions:
                tx['datetime'] = datetime.strptime(tx['date'], '%d-%b-%Y')
                tx['month'] = tx['datetime'].strftime('%b %Y')
                tx['category'] = classify_transaction_category(tx['narration'])
            
            # Aggregate by month for main chart
            monthly_data = {}
            for tx in transactions:
                month = tx['month']
                is_withdrawal = tx['is_withdrawal']
                
                if month not in monthly_data:
                    monthly_data[month] = {'Deposits': 0, 'Withdrawals': 0}
                
                if is_withdrawal:
                    monthly_data[month]['Withdrawals'] += tx['amount']
                else:
                    monthly_data[month]['Deposits'] += tx['amount']
            
            # Order months correctly
            months_ordered = sorted(monthly_data.keys(), key=lambda x: datetime.strptime(x, '%b %Y'))
            
            # Aggregate by category
            category_data = {}
            for tx in transactions:
                category = tx['category']
                if category not in category_data:
                    category_data[category] = 0
                category_data[category] += tx['amount']
            
            viz_data = {
                "type": "financial_analysis",
                "title": "Transaction Analysis",
                "x": months_ordered,
                "series": [
                    {"name": "Deposits", "values": [monthly_data[m]['Deposits'] for m in months_ordered]},
                    {"name": "Withdrawals", "values": [monthly_data[m]['Withdrawals'] for m in months_ordered]}
                ],
                "categories": {
                    "labels": list(category_data.keys()),
                    "values": list(category_data.values())
                }
            }

            return jsonify({
                "status": "success",
                "payload": viz_data,
                "generated_at": datetime.utcnow().isoformat() + "Z"
            })

        amount_cols = [col for col in df.columns if any(word in col.lower() 
                       for word in ['amount', 'debit', 'credit', 'balance'])]
        
        date_cols = [col for col in df.columns if 'date' in col.lower()]
        desc_cols = [col for col in df.columns if any(word in col.lower() for word in ['description', 'narration', 'merchant', 'remarks', 'particulars'])]
        
        if not amount_cols or not date_cols:
            return jsonify({"status": "error", "message": "Required columns not found"}), 400
        
        df[date_cols[0]] = pd.to_datetime(df[date_cols[0]], errors='coerce')
        df = df.dropna(subset=[date_cols[0]])
        df = df.sort_values(date_cols[0])
        
        df['month'] = df[date_cols[0]].dt.to_period('M')
        
        # Aggregate by month
        monthly_data = df.groupby('month')[amount_cols].sum()
        months_ordered = [m.strftime('%b %Y') for m in monthly_data.index.to_timestamp()]
        
        # Classify by category if description column exists
        category_data = {}
        if desc_cols:
            desc_col = desc_cols[0]
            df['category'] = df[desc_col].fillna('').apply(classify_transaction_category)
            
            # Sum by category using first amount column
            category_sum = df.groupby('category')[amount_cols[0]].sum()
            category_data = {
                "labels": category_sum.index.tolist(),
                "values": category_sum.values.tolist()
            }
        else:
            # Fallback: use column names as categories when no description is available
            category_data = {
                "labels": [col.title() for col in amount_cols],
                "values": [monthly_data[col].sum() for col in amount_cols]
            }
        
        viz_data = {
            "type": "financial_analysis",
            "title": "Transaction Analysis",
            "x": months_ordered,
            "series": []
        }
        
        for col in amount_cols:
            viz_data["series"].append({
                "name": col.title(),
                "values": monthly_data[col].tolist()
            })
        
        viz_data["categories"] = category_data
        
        return jsonify({
            "status": "success",
            "payload": viz_data,
            "generated_at": datetime.utcnow().isoformat() + "Z"
        })
    
    except Exception as e:
        logger.error(f"Visualization data error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

def get_user_privacy_budget(email):
    try:
        from database import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT total_epsilon, queries_count FROM privacy_budgets WHERE user_email = %s",
                    (email,)
                )
                result = cur.fetchone()
                if result:
                    return {
                        "epsilon": float(result['total_epsilon']),
                        "queries": result['queries_count']
                    }
                return {"epsilon": 0.0, "queries": 0}
    except:
        return {"epsilon": 0.0, "queries": 0}

@app.errorhandler(413)
def too_large(e):
    return jsonify({"status": "error", "message": "File too large. Maximum size is 16MB."}), 413

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({"status": "error", "message": "API endpoint not found"}), 404
    return "404 - Page not found", 404

@app.errorhandler(500)
def internal_error(e):
    logger.exception("Internal server error")
    return jsonify({"status": "error", "message": "Internal server error occurred"}), 500

if __name__ == "__main__":
    init_pool()
    initialize_he_context()
    
    logger.info("🚀 Starting FINGPT Privacy-Preserving LLM Server...")
    logger.info(f"📁 Upload folder: {UPLOAD_FOLDER}")
    logger.info(f"🤖 Ollama URL: {OLLAMA_URL}")
    logger.info(f"🧠 AI Model: {OLLAMA_MODEL}")
    logger.info(f"🌐 Access at: http://127.0.0.1:5000")
    
    try:
        test_response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if test_response.status_code == 200:
            logger.info("✅ Ollama connection successful")
        else:
            logger.warning("⚠️ Ollama returned non-200 status")
    except:
        logger.error("❌ Cannot connect to Ollama - start it with 'ollama serve'")
    
    fl_status = check_fl_status()
    if fl_status.get("status") == "running":
        logger.info("✅ FL environment connected")
    else:
        logger.warning("⚠️ FL environment not available - start with 'python secure_api/app.py'")
    
    try:
        app.run(debug=True, port=5000, host="127.0.0.1")
    finally:
        close_pool()