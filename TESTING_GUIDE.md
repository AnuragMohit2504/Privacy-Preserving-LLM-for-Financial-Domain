# FINGPT Complete Testing Guide

## Prerequisites

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start PostgreSQL (make sure fingpt database exists)
# 3. Run schema
psql -U postgres -d fingpt -f fingpt_schema.sql

# 4. Start Ollama
ollama serve

# 5. In another terminal, start FL server
cd layer2_fl/secure_api && python app.py

# 6. In another terminal, start HE server (optional)
python layer2_fl/he/he_server.py

# 7. Start main app
python app.py
```

---

## Feature 1: User Authentication

**What it does:** Login, signup, logout with password hashing

**How to test:**
1. Open `http://127.0.0.1:5000`
2. Click Signup → Create account with email/password
3. Login with credentials
4. Check database: `SELECT * FROM users;`

**Expected:** Account created, login successful, audit log entry created

---

## Feature 2: File Upload

**What it does:** Upload CSV, PDF, Excel files for analysis

**How to test:**
1. Login → Dashboard
2. Click upload button → Select `payslips.csv` or any bank statement PDF
3. Check response shows file_id, file_type, available actions

**API Test:**
```bash
curl -X POST -F "file=@payslips.csv" http://127.0.0.1:5000/api/upload \
  -H "Cookie: session=YOUR_SESSION_COOKIE"
```

**Expected:** File saved to `uploads/`, entry in `uploaded_files` table

---

## Feature 3: AI Chat & Financial Analysis

**What it does:** Chat with LLM (llama3.2) for financial insights

**How to test:**
1. Upload a bank statement CSV or PDF
2. Type: "analyze my bank statement"
3. Type: "create a budget plan"
4. Type: "show me my dashboard"

**API Test:**
```bash
curl -X POST http://127.0.0.1:5000/api/chat \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{"message": "analyze my bank statement", "filename": "your_file.csv"}'
```

**Expected:** HTML-formatted analysis with account summary, spending categories, insights

---

## Feature 4: Fraud / Anomaly Detection (NEW)

**What it does:** Algorithmic detection of suspicious financial records using Isolation Forest + Autoencoder ensemble

**How to test via Chat:**
1. Upload `payslips.csv` or any CSV with numeric columns
2. Type: "detect fraud" or "find unusual transactions" or "anomaly detection"
3. The system runs the ensemble and returns:
   - Total records analyzed
   - Number of anomalies detected
   - Outlier ratio (%)
   - Mean reconstruction error
   - Flagged record indices

**How to test via API (with supervised metrics):**
```bash
curl -X POST http://127.0.0.1:5000/api/fraud_benchmark \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{"filename": "payslips.csv", "fraud_rate": 0.05}'
```

**Expected Response:**
```json
{
  "status": "success",
  "data": {
    "n_samples": 1000,
    "n_anomalies_detected": 47,
    "outlier_ratio": 0.047,
    "mean_reconstruction_error": 0.0234,
    "precision": 0.85,
    "recall": 0.72,
    "f1_score": 0.78,
    "accuracy": 0.96,
    "supervised_mode": true
  }
}
```

**Direct Script Test:**
```bash
cd layer2_fl
python test_fraud_detection.py
```

**Expected:** Console output with metrics + `fraud_detection_results.json` file created

---

## Feature 5: Federated Learning (FL) Training

**What it does:** Privacy-preserving model training across users without sharing raw data

**How to test:**
1. Upload a CSV file
2. Type: "start fl training" or "submit for federated learning"
3. The system extracts features, encrypts them, and submits to FL server

**API Test:**
```bash
curl -X POST http://127.0.0.1:5000/api/chat \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{"message": "start fl training", "filename": "your_file.csv"}'
```

**Check FL Status:**
```bash
curl http://127.0.0.1:5000/api/fl_status \
  -H "Cookie: session=YOUR_SESSION_COOKIE"
```

**Trigger Training Round:**
```bash
curl -X POST http://127.0.0.1:5000/api/trigger_round \
  -H "Cookie: session=YOUR_SESSION_COOKIE"
```

**Expected:** Features submitted, privacy budget updated, training round logged

---

## Feature 6: Homomorphic Encryption (HE) — Optional

**What it does:** Encrypts feature vectors so server cannot see raw values

**How to test:**

**Step 1:** Start HE server
```bash
python layer2_fl/he/he_server.py
```

**Step 2:** Initialize context
```bash
curl -X POST http://127.0.0.1:9000/init_context \
  -H "Content-Type: application/json" \
  -d '{"poly_modulus_degree": 8192, "coeff_mod_bit_sizes": [60,40,40,60]}'
```

**Step 3:** Test encryption
```bash
curl -X POST http://127.0.0.1:9000/encrypt \
  -H "Content-Type: application/json" \
  -d '{"features": [1.5, 2.3, 4.1, 0.8]}'
```

**Step 4:** Run HE evaluator
```bash
python layer2_fl/he/he_evaluator.py
```

**Expected:**
- HE server returns encrypted vectors (base64 strings)
- Evaluator prints encryption/decryption times, ciphertext expansion ratio
- If TenSEAL not installed, graceful fallback to mock encryption

---

## Feature 7: LLM Privacy Auditing (NEW)

**What it does:** Measures and improves privacy of every chat interaction since Ollama provides no native privacy budget

**How to test:**

**Test 1 — Normal query (low risk)**
```bash
curl -X POST http://127.0.0.1:5000/api/chat \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{"message": "What is a mutual fund?"}'
```
**Expected:** Normal response, no privacy warning

**Test 2 — High-risk query (PII exposure)**
```bash
curl -X POST http://127.0.0.1:5000/api/chat \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{"message": "My name is Anurag Mohit and my email is anurag@example.com and my salary is 50000"}'
```
**Expected:** Response includes `privacy` field with warning:
```json
{
  "data": {
    "reply": "...",
    "privacy": {
      "privacy_warning": true,
      "risk_score": 45,
      "risk_level": "high",
      "recommendations": ["Avoid sharing PII in queries", "Use general terms instead of specific values"]
    }
  }
}
```

**Test 3 — Check privacy status**
```bash
curl http://127.0.0.1:5000/api/privacy_status \
  -H "Cookie: session=YOUR_SESSION_COOKIE"
```

**Expected:**
```json
{
  "status": "success",
  "data": {
    "total_queries_audited": 5,
    "average_risk_score": 23.5,
    "latest_risk_level": "medium",
    "latest_cumulative_epsilon": 2.34,
    "recent_logs": [...]
  }
}
```

**Test 4 — Verify database logging**
```sql
SELECT * FROM llm_privacy_logs WHERE user_email = 'your@email.com' ORDER BY created_at DESC;
```

**Expected:** Rows with risk_score, pii_count, synthetic_epsilon, sanitization_actions

---

## Feature 8: Data Visualization

**What it does:** Charts for income vs expenses, spending categories, merchant analysis

**How to test:**
1. Upload a CSV with columns: Date, Description, Debit, Credit, Balance
2. The dashboard automatically shows charts
3. Or call API:

```bash
curl "http://127.0.0.1:5000/api/vizdata?filename=your_file.csv&period=monthly" \
  -H "Cookie: session=YOUR_SESSION_COOKIE"
```

**Expected:** JSON with monthly deposits/withdrawals, category breakdown, top merchants

---

## Feature 9: Audit Logging

**What it does:** Tracks all user actions for compliance

**How to test:**
```bash
curl http://127.0.0.1:5000/api/audit_logs \
  -H "Cookie: session=YOUR_SESSION_COOKIE"
```

**Database check:**
```sql
SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 10;
```

**Expected:** Entries for USER_LOGIN, FILE_UPLOAD, FL_ROUND_TRIGGERED, etc.

---

## Feature 10: Privacy Budget Tracking

**What it does:** Tracks differential privacy epsilon consumption per user

**How to test:**
1. Do multiple FL training submissions
2. Check budget:

```bash
curl http://127.0.0.1:5000/api/fl_status \
  -H "Cookie: session=YOUR_SESSION_COOKIE"
```

**Database check:**
```sql
SELECT * FROM privacy_budgets WHERE user_email = 'your@email.com';
```

**Expected:** epsilon increases with each training round

---

## Complete End-to-End Test Script

Save this as `test_all.sh` and run:

```bash
#!/bin/bash

BASE="http://127.0.0.1:5000"
COOKIE="session=YOUR_SESSION_COOKIE_HERE"

echo "=== 1. Upload File ==="
curl -s -X POST -F "file=@payslips.csv" "$BASE/api/upload" -H "Cookie: $COOKIE" | python -m json.tool

echo -e "\n=== 2. Chat - General Question ==="
curl -s -X POST "$BASE/api/chat" \
  -H "Content-Type: application/json" -H "Cookie: $COOKIE" \
  -d '{"message": "What is a good savings rate?"}' | python -m json.tool

echo -e "\n=== 3. Chat - Fraud Detection ==="
curl -s -X POST "$BASE/api/chat" \
  -H "Content-Type: application/json" -H "Cookie: $COOKIE" \
  -d '{"message": "detect fraud", "filename": "payslips.csv"}' | python -m json.tool

echo -e "\n=== 4. Fraud Benchmark ==="
curl -s -X POST "$BASE/api/fraud_benchmark" \
  -H "Content-Type: application/json" -H "Cookie: $COOKIE" \
  -d '{"filename": "payslips.csv", "fraud_rate": 0.05}' | python -m json.tool

echo -e "\n=== 5. FL Status ==="
curl -s "$BASE/api/fl_status" -H "Cookie: $COOKIE" | python -m json.tool

echo -e "\n=== 6. Privacy Status ==="
curl -s "$BASE/api/privacy_status" -H "Cookie: $COOKIE" | python -m json.tool

echo -e "\n=== 7. Audit Logs ==="
curl -s "$BASE/api/audit_logs" -H "Cookie: $COOKIE" | python -m json.tool

echo -e "\n=== All Tests Complete ==="
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Ollama connection error" | Run `ollama serve` in a separate terminal |
| "FL server offline" | Start it: `cd layer2_fl/secure_api && python app.py` |
| "HE server not reachable" | Start it: `python layer2_fl/he/he_server.py` (optional) |
| "No module named 'presidio'" | Run `pip install presidio-analyzer presidio-anonymizer` |
| "No numeric columns for fraud" | Upload a CSV with numeric columns (Amount, Debit, Credit, etc.) |
| Database errors | Ensure PostgreSQL is running and schema is applied |

---

## Summary of All Features

| # | Feature | Status | How to Access |
|---|---------|--------|---------------|
| 1 | User Auth | ✅ Working | Web UI at `/login`, `/signup` |
| 2 | File Upload | ✅ Working | Web UI or `POST /api/upload` |
| 3 | AI Chat & Analysis | ✅ Working | Web UI chat or `POST /api/chat` |
| 4 | Fraud Detection | ✅ **NEW** | Chat: "detect fraud" or `POST /api/fraud_benchmark` |
| 5 | Federated Learning | ✅ Working | Chat: "start fl training" or `POST /api/trigger_round` |
| 6 | Homomorphic Encryption | ✅ **FIXED** | Optional server on port 9000 |
| 7 | LLM Privacy Audit | ✅ **NEW** | Automatic on every chat + `GET /api/privacy_status` |
| 8 | Data Visualization | ✅ Working | Dashboard charts or `GET /api/vizdata` |
| 9 | Audit Logging | ✅ Working | `GET /api/audit_logs` |
| 10 | Privacy Budget | ✅ Working | Tracked in `privacy_budgets` table |

