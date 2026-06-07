# FINGPT Performance Metrics

## 1. Fraud Detection Model (Isolation Forest + Autoencoder Ensemble)

### Benchmark Setup
- **Dataset:** `payslips.csv` (100 records, 16 numeric features)
- **Fraud Rate:** 9.00% (9 synthetic fraud labels out of 100)
- **Train/Test Split:** 80/20 (stratified)
- **Model:** IsolationForest (40% weight) + Autoencoder (60% weight)
- **Autoencoder:** 50 epochs, Adam optimizer, MSE loss
- **Device:** CPU

### Training Set Metrics (80 samples)
| Metric | Value |
|--------|-------|
| **Accuracy** | **97.50%** |
| **Precision** | **85.71%** |
| **Recall** | **85.71%** |
| **F1-Score** | **85.71%** |
| **ROC-AUC** | **97.06%** |
| **PR-AUC** | **88.44%** |
| False Positive Rate | 1.37% |
| Detection Rate @ 1% FPR | 71.43% |
| Detection Rate @ 5% FPR | 85.71% |
| Outlier Ratio | 8.75% |
| Mean Reconstruction Error | 0.037970 |
| Std Reconstruction Error | 0.047408 |
| Anomaly Score Threshold | 0.353535 |

**Confusion Matrix (Train):**
- True Positives: 6
- False Positives: 1
- True Negatives: 72
- False Negatives: 1

### Test Set Metrics (20 samples - very small sample)
| Metric | Value |
|--------|-------|
| **Accuracy** | **80.00%** |
| **Precision** | **25.00%** |
| **Recall** | **50.00%** |
| **F1-Score** | **33.33%** |
| **ROC-AUC** | **86.11%** |
| **PR-AUC** | **36.67%** |
| False Positive Rate | 16.67% |
| Detection Rate @ 1% FPR | 0.00% |
| Detection Rate @ 5% FPR | 0.00% |
| Outlier Ratio | 20.00% |
| Mean Reconstruction Error | 0.141121 |
| Std Reconstruction Error | 0.126324 |

**Confusion Matrix (Test):**
- True Positives: 1
- False Positives: 3
- True Negatives: 15
- False Negatives: 1

### Full Dataset Metrics (100 samples)
| Metric | Value |
|--------|-------|
| **Accuracy** | **92.00%** |
| **Precision** | **60.00%** |
| **Recall** | **33.33%** |
| **F1-Score** | **42.86%** |
| **ROC-AUC** | **95.36%** |
| **PR-AUC** | **57.27%** |
| False Positive Rate | 2.20% |
| Detection Rate @ 5% FPR | 88.89% |
| Outlier Ratio | 5.00% |
| Mean Reconstruction Error | 0.058600 |

### Key Observations
1. **Small Dataset Limitation:** The test set has only 20 samples (2 fraud cases), making test metrics unreliable. The model shows signs of overfitting to the small training set.
2. **Train Performance:** Excellent train metrics (97.5% accuracy, 97% ROC-AUC) indicate the ensemble architecture works well when given sufficient data.
3. **Reconstruction Error Gap:** Train MRE (0.038) vs Test MRE (0.141) suggests the autoencoder overfits to training patterns.
4. **Recommendation:** For production deployment, use a dataset with at least 1,000+ samples to get stable test metrics.

---

## 2. Federated Learning Model (SGDClassifier)

### Architecture
- **Algorithm:** SGDClassifier with `loss="log_loss"` (logistic regression)
- **Training:** `partial_fit()` for online learning
- **Privacy:** Laplace noise added (DP_NOISE_STD = 0.01)
- **Classes:** Binary classification (0 = unstable, 1 = stable financial health)

### Performance Characteristics
- **Accuracy:** Variable per round (computed on buffered features after each training round)
- **No fixed baseline:** Accuracy depends entirely on the quality and quantity of feature vectors submitted by clients
- **Privacy Budget (ε):** Accumulates per round based on `sqrt(num_samples) * noise_std * 10`

### Example Round Output
```json
{
  "status": "success",
  "round": 5,
  "features_processed": 12,
  "accuracy": 0.75,
  "epsilon": 2.34
}
```

### Limitations
- The FL model is a simple linear classifier (SGD), not a deep neural network
- Accuracy is self-reported on the same buffered data used for training (no hold-out test set)
- For meaningful FL accuracy, multiple clients need to submit diverse feature vectors

---

## 3. Homomorphic Encryption Performance

### Configuration
- **Scheme:** CKKS (TenSEAL)
- **Poly Modulus Degree:** 8192
- **Coeff Mod Bit Sizes:** [60, 40, 40, 60]
- **Global Scale:** 2^40

### Performance Metrics (from `he_evaluator.py`)
The HE evaluator measures:

| Metric | Description |
|--------|-------------|
| Encryption Time | Time to encrypt a feature vector |
| Decryption Time | Time to decrypt ciphertext back to plaintext |
| Aggregation Time | Time to homomorphically add/average ciphertexts |
| Ciphertext Size | Size of encrypted data in bytes |
| Expansion Ratio | Ciphertext size / Original plaintext size |
| Accuracy Loss | Max error between original and decrypted values |

### Typical CKKS Overhead
- **Ciphertext Expansion:** ~100-400x (depends on poly_modulus_degree)
- **Encryption Time:** ~10-100ms per vector (depends on vector length)
- **Accuracy Loss:** < 0.001 (with proper parameter tuning)

### Fallback Mode
If TenSEAL is not installed, the HE server runs in **MOCK mode**:
- Encryption: `f * 2 + 1` (simple obfuscation)
- Decryption: `(v - 1) / 2`
- No real security, but API-compatible for testing

---

## 4. LLM Privacy Audit Metrics

### Synthetic Privacy Budget (ε)
| Parameter | Value |
|-----------|-------|
| Default Budget per User | 10.0 |
| Base Cost per Query | 0.1 |
| PII Multiplier | 2.0x |
| High-Risk PII Multiplier | Additional 2.0x |
| Repetition Multiplier | 1.5x |
| Time Decay (>1 hour) | 0.5x |
| Budget Exhaustion Penalty (>80%) | 2.0x |

### Risk Scoring
| Component | Weight | Range |
|-----------|--------|-------|
| PII Density | 40% | 0-40 points |
| Query Specificity | 30% | 0-30 points |
| Memorization Risk | 30% | 0-30 points |
| **Total Risk Score** | **100%** | **0-100** |

### Risk Levels
- **LOW:** 0-25
- **MEDIUM:** 26-50
- **HIGH:** 51-75
- **CRITICAL:** 76-100

---

## 5. System Performance

### Flask App (`app.py`)
- **Max File Upload:** 16 MB
- **Supported Formats:** CSV, PDF, XLSX, XLS
- **LLM Timeout:** 60 seconds per query
- **Data Preview Limit:** 50 rows for LLM context
- **Fraud Detection Limit:** 5,000 rows max (truncates larger files)

### Database (`database.py`)
- **Connection Pool:** 1-20 connections (ThreadedConnectionPool)
- **Cursor Factory:** RealDictCursor

### Frontend (`dashboard.js`)
- **FL Status Update Interval:** 10 seconds
- **Chart Library:** Plotly.js 2.27.0
- **Theme:** Dark/Light mode with CSS variables

---

## 6. Recommendations for Improving Metrics

### Fraud Detection
1. **Increase Dataset Size:** Use 1,000+ samples for stable test metrics
2. **Address Overfitting:** Add dropout to autoencoder, use early stopping
3. **Hyperparameter Tuning:** Grid search over `if_contamination`, `ensemble_weight_if`, `ae_epochs`
4. **Cross-Validation:** Use 5-fold CV instead of single train/test split

### Federated Learning
1. **Better Model:** Replace SGDClassifier with a small neural network
2. **Test Set:** Hold out a separate test set for unbiased accuracy estimation
3. **More Clients:** Need 5+ diverse clients for meaningful FL aggregation
4. **Convergence:** Track accuracy over rounds to ensure convergence

### Homomorphic Encryption
1. **Install TenSEAL:** `pip install tenseal` for real encryption
2. **Parameter Tuning:** Reduce `poly_modulus_degree` to 4096 for faster encryption
3. **Batching:** Encrypt multiple vectors in a single ciphertext (SIMD-style)

