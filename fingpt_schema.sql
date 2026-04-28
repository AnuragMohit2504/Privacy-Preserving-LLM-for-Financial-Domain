-- FINGPT application schema
-- This schema matches the Flask app and FL helper modules.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    user_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    fl_consent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS uploaded_files (
    id SERIAL PRIMARY KEY,
    user_email TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    file_path TEXT NOT NULL,
    uploaded_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    user_email TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
    file_id INTEGER REFERENCES uploaded_files(id) ON DELETE SET NULL,
    message TEXT NOT NULL,
    sender TEXT NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id SERIAL PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES uploaded_files(id) ON DELETE CASCADE,
    analysis_type TEXT NOT NULL,
    result_data JSONB NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    action TEXT NOT NULL,
    details TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS privacy_budgets (
    user_email TEXT PRIMARY KEY REFERENCES users(email) ON DELETE CASCADE,
    total_epsilon DOUBLE PRECISION NOT NULL DEFAULT 0,
    queries_count INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS training_rounds (
    id SERIAL PRIMARY KEY,
    client_id TEXT NOT NULL,
    round_no INTEGER NOT NULL,
    epsilon DOUBLE PRECISION NOT NULL,
    accuracy DOUBLE PRECISION,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    uploaded_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS encrypted_exports (
    export_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_uuid UUID NOT NULL REFERENCES users(user_uuid) ON DELETE CASCADE,
    feature_dim INTEGER NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_uploaded_files_user_email
    ON uploaded_files(user_email);

CREATE INDEX IF NOT EXISTS idx_chat_history_user_email_created_at
    ON chat_history(user_email, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_results_file_id
    ON analysis_results(file_id);

CREATE TABLE IF NOT EXISTS llm_privacy_logs (
    id SERIAL PRIMARY KEY,
    user_email TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    risk_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    risk_level TEXT NOT NULL DEFAULT 'low',
    pii_count INTEGER NOT NULL DEFAULT 0,
    synthetic_epsilon DOUBLE PRECISION,
    cumulative_epsilon DOUBLE PRECISION,
    sanitization_actions JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_llm_privacy_logs_user_email
    ON llm_privacy_logs(user_email, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_training_rounds_created_at
    ON training_rounds(created_at DESC);
