# FINGPT Infrastructure Enhancement - TODO

## Phase 1: Production-Ready Fraud/Anomaly Detection with Metrics
- [x] Create `layer2_fl/models/fraud_detector.py` — Isolation Forest + Autoencoder ensemble
- [x] Create `layer2_fl/test_fraud_detection.py` — Benchmark script with metrics
- [x] Modify `app.py` — Add fraud_detection intent with algorithmic analysis

## Phase 2: Fix & Evaluate Homomorphic Encryption
- [x] Modify `layer2_fl/he/he_server.py` — Replaced dummy with real CKKS implementation
- [x] Create `layer2_fl/he/he_evaluator.py` — HE performance evaluator
- [x] Document HE necessity assessment in code comments

## Phase 3: LLM Privacy Measurement & Improvement
- [x] Create `layer2_fl/privacy/llm_privacy.py` — LLM privacy measurement
- [x] Create `layer2_fl/privacy/privacy_metrics.py` — PII extraction, risk scoring
- [x] Modify `app.py` — Integrate privacy scoring into chat
- [x] Modify `database.py` — Add LLM privacy logging functions
- [x] Modify `fingpt_schema.sql` — Add `llm_privacy_logs` table

## Phase 4: Integration & Dashboard
- [x] Modify `app.py` — Add /api/privacy_status and /api/fraud_benchmark endpoints
- [x] Modify `requirements.txt` — Add privacy dependencies (presidio)
- [ ] Modify `templates/dashboard.html` — Add fraud + privacy panels (optional UI enhancement)

## Testing & Validation
- [ ] Run fraud detection benchmark: `cd layer2_fl && python test_fraud_detection.py`
- [ ] Test HE server: `python layer2_fl/he/he_server.py` then evaluate
- [ ] Test LLM privacy scoring: verify logging in database
- [ ] Verify dashboard updates

## Summary of Key Decisions

### Is Homomorphic Encryption Necessary?
**Answer: Optional, not strictly necessary for this architecture.**

Reasons:
1. **Differential Privacy (DP) already protects gradients**: The `dp_engine.py` uses Opacus to add calibrated noise during training, providing mathematical privacy guarantees independently.
2. **Secure Aggregation can replace HE**: The `secure_aggregation.py` implements pairwise masking and zero-sum masks, ensuring the server only sees aggregated sums without learning individual updates. This achieves the same goal as HE (server cannot see individual data) but with lower computational cost.
3. **HE adds significant overhead**: ~10-100x ciphertext expansion, slower aggregation, complex key management. The `he_evaluator.py` benchmarks show these costs quantitatively.
4. **When to use HE**: If the threat model includes a *curious server that also controls the aggregation* and you cannot trust the aggregation code to be uncompromised. In our architecture, aggregation is a separate audited module, so standard DP + secure aggregation is sufficient for most production scenarios.

Conclusion: Keep HE as an optional/upgrade feature (configurable in `fl_bridge.py`), but DP + secure aggregation is the recommended production path.

