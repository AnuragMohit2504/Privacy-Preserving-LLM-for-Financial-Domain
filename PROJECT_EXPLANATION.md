# FINGPT - Privacy-Preserving Financial AI Assistant
## Complete Project Structure & Working Explanation

---

## 1. PROJECT OVERVIEW

**FINGPT** is a privacy-preserving financial document analysis system that combines:
- **Local LLM inference** (Ollama with llama3.2) for financial analysis
- **Federated Learning (FL)** for privacy-preserving model training across users
- **Homomorphic Encryption (HE)** for encrypting feature vectors before sharing
- **Differential Privacy (DP)** with privacy budget tracking per user
- **Fraud/Anomaly Detection** using Isolation Forest + Autoencoder ensemble
- **LLM Privacy Auditing** to measure and mitigate PII leakage risks

**Core Idea:** Users upload bank statements, payslips, or transaction CSVs. The AI analyzes them while NEVER exposing raw personal data to external services. Sensitive features are extracted locally, encrypted with HE, and submitted to a federated learning server where aggregation happens on ciphertext.

---

## 2. TECH STACK

| Layer | Technology |
|-------|-----------|
| Web Backend | Flask (Python) |
| Database | PostgreSQL with psycopg2 connection pooling |
| LLM Engine | Ollama (local, runs llama3.2:latest) |
| ML/AI | PyTorch, scikit-learn, pandas, numpy |
| Encryption | TenSEAL (CKKS homomorphic encryption) |
| FL Framework | Flower (flwr) |
| Differential Privacy | Opacus |
| Frontend | HTML + CSS + Vanilla JavaScript (Plotly.js for charts) |
| PDF Parsing | PyPDF2, pdfplumber, PyMuPDF (fitz) |
| PII Detection | Presidio (Microsoft) |

---

## 3. DIRECTORY STRUCTURE

```
FINGPT_MAJOR_PROJECT/
│
├── app.py                          # Main Flask application (entry point)
├── database.py                     # PostgreSQL connection pool & all DB operations
├── analyzer.py                     # Standalone financial document analyzer (batch processing)
├── feature_extractor.py            # Extracts numeric feature vectors from PDF/CSV/Excel
├── fl_bridge.py                    # HTTP bridge between Flask app and FL/HE servers
├── fingpt_schema.sql               # PostgreSQL database schema
├── requirements.txt                # Python dependencies
├── TESTING_GUIDE.md                # Complete testing instructions
│
├── layer2_fl/                      # Federated Learning & Privacy Layer
│   ├── __init__.py
│   ├── client.py                   # FL client implementation
│   ├── server.py                   # Flower FL server coordinator
│   ├── fl_config.py                # FL hyperparameters (rounds, clients, etc.)
│   ├── test_*.py                   # Various test scripts
│   │
│   ├── aggregation/
│   │   └── secure_aggregation.py   # Secure mean aggregation on encrypted weights
│   │
│   ├── db/
│   │   ├── audit.py                # Audit logging for FL actions
│   │   └── postgres.py             # FL-specific PostgreSQL helpers
│   │
│   ├── dp/
│   │   └── dp_engine.py            # Differential Privacy engine using Opacus
│   │
│   ├── experimental_fl/            # Experimental FL implementations
│   │   ├── client.py, server.py, model.py, train.py
│   │
│   ├── he/
│   │   ├── he_server.py            # FastAPI server for Homomorphic Encryption (TenSEAL CKKS)
│   │   ├── he_evaluator.py         # HE performance evaluator
│   │   └── he_utils.py             # HE helper functions (commented out)
│   │
│   ├── models/
│   │   ├── expense_model.py        # PyTorch Autoencoder + Attention-based classifier
│   │   ├── expense_classifier.py   # Expense classification logic
│   │   └── fraud_detector.py       # Production fraud detector (Isolation Forest + Autoencoder)
│   │
│   ├── privacy/
│   │   ├── llm_privacy.py          # LLM Privacy Auditor (synthetic epsilon, PII scoring)
│   │   └── privacy_metrics.py      # Privacy risk scoring, sanitization, deduplication
│   │
│   └── secure_api/
│       ├── app.py                  # Secure FL API server
│       ├── aggregator.py           # Model aggregation logic
│       └── status.py               # FL status reporting
│
├── static/                         # Frontend assets
│   ├── css/
│   │   ├── styles.css              # Login/signup styles
│   │   └── dashboard.css           # Dashboard & chat UI styles
│   ├── js/
│   │   ├── main.js                 # Login/signup page scripts
│   │   └── dashboard.js            # Main dashboard: chat, charts, FL monitoring
│   └── assets/
│       └── favicon.png
│
├── templates/                      # Jinja2 HTML templates
│   ├── index.html                  # Main dashboard (chat + visualization)
│   ├── login.html                  # Login page
│   ├── signup.html                 # Signup page
│   └── dashboard.html              # Alternative dashboard template
│
├── data/
│   └── generators/                 # Synthetic data generators
│       ├── bank_statement_gen.py   # Generates fake bank statement PDFs
│       ├── payslip_csv_gen.py      # Generates fake payslip CSVs
│       └── analyzer.py             # Batch analyzer for generated data
│
├── bank_statements/                # Sample bank statement PDFs
├── enhanced_bank_statements/       # Enhanced/generated bank statements
├── analysis_results/               # Output folder for batch analysis
├── documentation/                  # Project documentation, diagrams, certificates
└── uploads/                        # User-uploaded files (created at runtime)
```

---

## 4. CORE COMPONENTS EXPLAINED

### 4.1 Main Flask App (`app.py`)

**Role:** Central web server handling all HTTP requests, user sessions, file uploads, chat, and orchestrating AI analysis.

**Key Functions:**
- **Authentication:** Login/signup with Werkzeug password hashing, Flask-Login session management
- **File Upload:** Accepts CSV, PDF, XLSX, XLS (max 16MB). Saves to `uploads/` with sanitized filenames
- **AI Chat (`/api/chat`):** Routes user messages through intent detection:
  - `dashboard` → Returns dashboard navigation
  - `budget` → Generates budget plan via Ollama
  - `anomaly`/`fraud` → Runs fraud detection analysis
  - `fl training` → Extracts features, submits to FL server
  - `analyze` → Document analysis via Ollama
  - General questions → Direct LLM query
- **Privacy Guard:** System prompt prevents PII leakage. `should_block_sensitive_request()` blocks extraction attempts
- **Data Sanitization:** `sanitize_dataframe_for_llm()` drops sensitive columns, redacts emails/phones/IDs
- **Fraud Detection:** `run_fraud_detection_analysis()` uses Isolation Forest on numeric columns
- **Visualization:** `/api/vizdata` returns JSON for Plotly charts (income/expense, categories, merchants)

**External Services Called:**
- Ollama at `localhost:11434` for LLM inference
- FL Server at `localhost:8000` for federated learning
- HE Server at `localhost:9000` for encryption (optional)

### 4.2 Database Layer (`database.py`)

**Role:** PostgreSQL connection management and all CRUD operations.

**Key Features:**
- **ThreadedConnectionPool:** Min 1, max 20 connections with `get_db()` context manager
- **Tables Managed:**
  - `users` - accounts with UUID, email, name, password_hash, fl_consent
  - `uploaded_files` - file metadata (user_email, filename, type, size, path)
  - `chat_history` - message log with user/file linkage
  - `analysis_results` - AI analysis outputs as JSONB
  - `audit_logs` - compliance logging (USER_LOGIN, FILE_UPLOAD, FL_ROUND_TRIGGERED)
  - `privacy_budgets` - per-user epsilon tracking for differential privacy
  - `training_rounds` - FL round history (client_id, round_no, epsilon, accuracy)
  - `llm_privacy_logs` - privacy audit per chat interaction (risk_score, pii_count, epsilon)
  - `encrypted_exports` - HE export metadata

### 4.3 Feature Extractor (`feature_extractor.py`)

**Role:** Converts uploaded documents into numeric feature vectors for FL training.

**Flows:**
- **CSV/Excel:** Extracts sum/mean/std/max/min of amount/debit/credit/balance columns, transaction count, date range
- **PDF Bank Statement:** Parses text with regex, extracts Rs. amounts, categorizes into withdrawals/deposits/balances
- **PDF Payslip:** Extracts Basic, HRA, Gross, Net, CTC, PF, Tax, computes take-home ratio

**Output:** `(feature_vector: np.ndarray, features_dict: dict)` - vector goes to FL, dict is metadata

### 4.4 FL Bridge (`fl_bridge.py`)

**Role:** HTTP client that communicates between Flask app and the FL/HE microservices.

**Functions:**
- `check_fl_status()` → GET `localhost:8000/api/status`
- `submit_features_for_training()` → POST features to FL server
- `trigger_fl_round()` → POST to trigger manual training round
- `get_training_status()` → GET training progress
- `encrypt_features()` → POST to HE server at `localhost:9000/encrypt`
- `init_he_context()` → Initialize CKKS context with poly_modulus_degree=8192

### 4.5 Fraud Detector (`layer2_fl/models/fraud_detector.py`)

**Role:** Production anomaly detection for financial records.

**Architecture:**
1. **Isolation Forest** (40% weight) - Unsupervised outlier detection
2. **Autoencoder** (`ExpenseModel`, 60% weight) - Reconstruction error anomaly detection
3. **Ensemble** - Weighted combination of normalized scores

**Metrics Computed:**
- Unsupervised: outlier_ratio, mean/std reconstruction_error, anomaly_threshold
- Supervised (if labels): precision, recall, f1_score, accuracy, ROC-AUC, PR-AUC, confusion matrix
- Financial-specific: false_positive_rate, detection_rate_at_1%_FPR, detection_rate_at_5%_FPR

**Synthetic Label Generation:** `generate_synthetic_fraud_labels()` creates test labels based on:
- High pay + low days worked (ghost employee pattern)
- Unusually high deduction ratios
- Extreme bonus values

### 4.6 LLM Privacy Auditor (`layer2_fl/privacy/llm_privacy.py`)

**Role:** Since Ollama provides no native privacy budget, this implements proxy privacy measurement.

**Key Concepts:**
- **Synthetic Epsilon:** Heuristic privacy loss per query (NOT true DP epsilon)
  - Base cost: 0.1 per query
  - PII multiplier: 2x if query contains PII
  - High-risk PII (PAN, Aadhaar, account): additional 2x
  - Repetition multiplier: 1.5x for repeated queries
  - Time decay: 0.5x if last query > 1 hour ago
  - Budget exhaustion penalty: up to 2x when >80% budget used

- **Information Leakage Proxy:**
  - PII density in prompts (0-40 points)
  - Query specificity (numbers, length, proper nouns) (0-30 points)
  - Memorization risk (exact phrases from query appearing in response) (0-30 points)

- **Mitigations:**
  - Response sanitization when response_pii_count > 0
  - Aggressive sanitization when risk_score > 50
  - Query deduplication to prevent systematic extraction

**Audit Record:** Every chat interaction logs to `llm_privacy_logs` table with risk_score, risk_level, synthetic_epsilon, cumulative_epsilon, sanitization_actions.

### 4.7 Homomorphic Encryption Server (`layer2_fl/he/he_server.py`)

**Role:** FastAPI microservice for CKKS homomorphic encryption using TenSEAL.

**Endpoints:**
- `POST /init_context` - Initialize CKKS context (poly_modulus_degree=8192, coeff_mod_bit_sizes=[60,40,40,60])
- `POST /encrypt` - Encrypt float vector into CKKS ciphertext (chunked for large vectors)
- `POST /decrypt` - Decrypt ciphertext back to floats
- `POST /aggregate` - Homomorphically add and average multiple ciphertexts
- `GET /metrics` - Performance stats (encryption/decryption/aggregation times, ciphertext sizes)
- `GET /health` - Health check

**Fallback:** If TenSEAL not installed, runs in MOCK mode with simple obfuscation (x*2+1).

### 4.8 Differential Privacy Engine (`layer2_fl/dp/dp_engine.py`)

**Role:** Wraps PyTorch models with Opacus for DP-SGD training.

**Function:** `make_private(model, optimizer, dataloader, noise, max_norm)`
- Fixes unsupported layers (BatchNorm → GroupNorm)
- Attaches PrivacyEngine with noise_multiplier and max_grad_norm
- Returns private model, optimizer, dataloader, and privacy_engine

### 4.9 Secure Aggregation (`layer2_fl/aggregation/secure_aggregation.py`)

**Role:** Aggregates encrypted model updates without decryption.

**Function:** `secure_mean(enc_weights_list)`
- Sums encrypted weight vectors element-wise (homomorphic addition)
- Multiplies by 1/n (homomorphic scalar multiplication)
- Returns encrypted average

### 4.10 Frontend (`templates/index.html` + `static/js/dashboard.js`)

**Role:** Single-page dashboard application.

**Features:**
- **Chat Interface:** Message input, file attachment (drag & drop), typing indicators, action buttons
- **Visualization Panel:** Plotly.js charts (financial trends, category pie chart, merchant bar chart)
- **FL Monitor Tab:** Real-time status, training progress chart (accuracy/loss per round), privacy budget chart (epsilon consumption)
- **Analytics Tab:** Timeline, income vs expense, savings rate, category breakdown
- **Theme:** Dark/light mode toggle with CSS variables

**State Management (dashboard.js):**
```javascript
state = {
  uploadedFile, uploadedFileId, fileType,
  currentSection, flStatus, chatHistory, theme,
  roundHistory: { rounds: [], accuracy: [], epsilon: [] }
}
```

---

## 5. DATA FLOW

### 5.1 Normal Chat Flow
```
User → Browser → POST /api/chat (message, filename)
  → app.py
    → Intent detection
    → If has file: extract data preview (sanitize first)
    → query_ollama(prompt, system_prompt)
    → Privacy audit (llm_privacy.py)
    → Log to chat_history + llm_privacy_logs
    → Return HTML reply
```

### 5.2 Fraud Detection Flow
```
User: "detect fraud"
  → app.py
    → load_tabular_file() → extract_numeric_dataframe()
    → run_fraud_detection_analysis()
      → StandardScaler → IsolationForest.fit()
      → anomaly_scores, predictions
      → Build HTML results card
    → Return results with flagged row indices
```

### 5.3 Federated Learning Flow
```
User: "start fl training"
  → app.py
    → extract_features(filepath, file_type, analysis_type)
      → feature_vector (10-dim numpy array)
      → features_dict (metadata)
    → fl_bridge.submit_features_for_training()
      → POST localhost:8000/api/submit_features
    → FL Server aggregates with other clients
    → update_privacy_budget(user_email, 0.5)
    → Return FL status card
```

### 5.4 Homomorphic Encryption Flow
```
Feature Vector → he_server.py /encrypt
  → TenSEAL CKKS encryption
  → base64-encoded ciphertext chunks
  → Stored/transmitted encrypted
  → Aggregation: he_server.py /aggregate (homomorphic add + scalar multiply)
  → Decryption: he_server.py /decrypt (only with secret key)
```

---

## 6. DATABASE SCHEMA

```sql
-- Core tables
users (user_uuid UUID PK, email TEXT UNIQUE, name TEXT, password_hash TEXT, fl_consent BOOLEAN, created_at TIMESTAMP)
uploaded_files (id SERIAL PK, user_email FK, filename TEXT, original_filename TEXT, file_type TEXT, file_size BIGINT, file_path TEXT, uploaded_at TIMESTAMP, processed BOOLEAN)
chat_history (id SERIAL PK, user_email FK, file_id INTEGER FK, message TEXT, sender TEXT, created_at TIMESTAMP)
analysis_results (id SERIAL PK, file_id FK, analysis_type TEXT, result_data JSONB, created_at TIMESTAMP)
audit_logs (id SERIAL PK, action TEXT, details TEXT, created_at TIMESTAMP)
privacy_budgets (user_email PK FK, total_epsilon DOUBLE, queries_count INTEGER, last_updated TIMESTAMP)
training_rounds (id SERIAL PK, client_id TEXT, round_no INTEGER, epsilon DOUBLE, accuracy DOUBLE, created_at TIMESTAMP)
llm_privacy_logs (id SERIAL PK, user_email FK, query_text TEXT, response_text TEXT, risk_score DOUBLE, risk_level TEXT, pii_count INTEGER, synthetic_epsilon DOUBLE, cumulative_epsilon DOUBLE, sanitization_actions JSONB, created_at TIMESTAMP)
encrypted_exports (export_id UUID PK, user_uuid FK, feature_dim INTEGER, created_at TIMESTAMP)
```

---

## 7. API ENDPOINTS

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Redirect to login or dashboard |
| `/login` | GET/POST | User authentication |
| `/signup` | GET/POST | User registration |
| `/logout` | GET | Session termination |
| `/dashboard` | GET | Main dashboard page |
| `/api/upload` | POST | File upload (multipart/form-data) |
| `/api/chat` | POST | AI chat (JSON: message, filename, file_id) |
| `/api/files` | GET | List user's uploaded files |
| `/api/chat_history` | GET | Get chat history |
| `/api/audit_logs` | GET | Get audit logs |
| `/api/fl_status` | GET | FL server status + privacy budget |
| `/api/training_logs` | GET | FL training round history |
| `/api/trigger_round` | POST | Manually trigger FL round |
| `/api/preview` | GET | CSV/Excel preview (rows, columns) |
| `/api/vizdata` | GET | Chart data (financial trends, categories) |
| `/api/privacy_status` | GET | User's LLM privacy audit status |
| `/api/fraud_benchmark` | POST | Run fraud detection with synthetic labels |

---

## 8. HOW TO RUN

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Setup PostgreSQL
createdb fingpt
psql -U postgres -d fingpt -f fingpt_schema.sql

# 3. Start Ollama (in terminal 1)
ollama serve

# 4. Start FL server (in terminal 2)
cd layer2_fl/secure_api && python app.py

# 5. Start HE server (optional, in terminal 3)
python layer2_fl/he/he_server.py

# 6. Start main app (in terminal 4)
python app.py
# Access at http://127.0.0.1:5000
```

---

## 9. KEY FEATURES SUMMARY

| # | Feature | Implementation |
|---|---------|---------------|
| 1 | **User Auth** | Flask-Login + Werkzeug hashing |
| 2 | **File Upload** | Secure filename, 16MB limit, CSV/PDF/XLSX |
| 3 | **AI Chat** | Ollama llama3.2 with privacy system prompt |
| 4 | **Bank Statement Analysis** | PDF text extraction → Ollama HTML analysis |
| 5 | **Payslip Analysis** | CSV parsing → salary structure breakdown |
| 6 | **Fraud Detection** | Isolation Forest + Autoencoder ensemble |
| 7 | **Data Visualization** | Plotly.js charts from /api/vizdata |
| 8 | **Federated Learning** | Flower framework + feature extraction |
| 9 | **Homomorphic Encryption** | TenSEAL CKKS (or mock fallback) |
| 10 | **Differential Privacy** | Opacus DP-SGD + privacy budget tracking |
| 11 | **LLM Privacy Audit** | Synthetic epsilon, PII scoring, sanitization |
| 12 | **Audit Logging** | All actions logged to PostgreSQL |
| 13 | **Privacy Guard** | Blocks PII extraction attempts, redacts sensitive data |

---

## 10. PRIVACY MECHANISMS

1. **Input Sanitization:** Sensitive columns dropped before LLM context. Emails, phones, PAN, Aadhaar redacted with regex.
2. **System Prompt Guard:** Hardcoded instructions prevent revealing raw data, PII, or system internals.
3. **Query Blocking:** `should_block_sensitive_request()` detects extraction attempts ("dump all emails", "list salaries", "ignore previous instructions").
4. **Privacy Budget:** Per-user epsilon tracking in `privacy_budgets` table. Increases with each FL submission.
5. **LLM Privacy Audit:** Every interaction scored for PII leakage, memorization risk, query diversity. High-risk responses sanitized.
6. **Federated Learning:** Raw data never leaves server. Only 10-dim feature vectors are shared (optionally HE-encrypted).
7. **Homomorphic Encryption:** Feature vectors encrypted with CKKS before transmission. Server aggregates ciphertext without decryption.

---

*This document provides a complete overview of the FINGPT project architecture, components, data flows, and privacy mechanisms. Use it to understand how the system works end-to-end.*

