import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from contextlib import contextmanager
import os
import json
from datetime import datetime

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "fingpt"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "admin"),
}

connection_pool = None

def init_pool():
    global connection_pool
    connection_pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=20,
        **DB_CONFIG,
        cursor_factory=RealDictCursor
)
    

def get_connection():
    global connection_pool

    if connection_pool is None:
        init_pool()

    try:
        return connection_pool.getconn()
    except psycopg2.pool.PoolError:
        init_pool()
        return connection_pool.getconn()

def return_connection(conn):
    if connection_pool and conn:
        try:
            connection_pool.putconn(conn)
        except:
            pass

@contextmanager
def get_db():
    conn = None
    try:
        conn = get_connection()
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        raise e
    finally:
        if conn:
            try:
                return_connection(conn)
            except:
                pass
def get_user(email):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            return cur.fetchone()

def create_user(email, name, password_hash):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (email, name, password_hash) VALUES (%s, %s, %s)",
                (email, name, password_hash)
            )

def log_file_upload(user_email, filename, original_filename, file_type, file_size, file_path):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO uploaded_files 
                   (user_email, filename, original_filename, file_type, file_size, file_path) 
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                (user_email, filename, original_filename, file_type, file_size, file_path)
            )
            return cur.fetchone()['id']

def log_chat_message(user_email, message, sender, file_id=None):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO chat_history (user_email, file_id, message, sender) 
                   VALUES (%s, %s, %s, %s)""",
                (user_email, file_id, message, sender)
            )

def log_analysis_result(file_id, analysis_type, result_data):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO analysis_results (file_id, analysis_type, result_data) 
                   VALUES (%s, %s, %s)""",
                (file_id, analysis_type, psycopg2.extras.Json(result_data))
            )

def insert_audit_log(action, details=None):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_logs (action, details) VALUES (%s, %s)",
                (action, details)
            )

def table_has_column(conn, table_name, column_name):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT 1
               FROM information_schema.columns
               WHERE table_name = %s AND column_name = %s""",
            (table_name, column_name)
        )
        return cur.fetchone() is not None

def log_training_round(client_id, round_no, epsilon, accuracy=None):
    with get_db() as conn:
        with conn.cursor() as cur:
            if table_has_column(conn, "training_rounds", "accuracy"):
                cur.execute(
                    """INSERT INTO training_rounds (client_id, round_no, epsilon, accuracy)
                       VALUES (%s, %s, %s, %s)""",
                    (client_id, round_no, float(epsilon), accuracy)
                )
            else:
                cur.execute(
                    """INSERT INTO training_rounds (client_id, round_no, epsilon)
                       VALUES (%s, %s, %s)""",
                    (client_id, round_no, float(epsilon))
                )
def get_training_rounds(limit=50):
    with get_db() as conn:
        with conn.cursor() as cur:
            accuracy_expr = "accuracy" if table_has_column(conn, "training_rounds", "accuracy") else "NULL AS accuracy"
            cur.execute(
                f"""SELECT client_id, round_no, epsilon, {accuracy_expr}, created_at
                    FROM training_rounds
                    ORDER BY created_at DESC
                    LIMIT %s""",
                (limit,)
            )
            return cur.fetchall()

def get_audit_logs(limit=50):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT action, details, created_at
                   FROM audit_logs
                   ORDER BY created_at DESC
                   LIMIT %s""",
                (limit,)
            )
            return cur.fetchall()

def update_privacy_budget(user_email, epsilon_used):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO privacy_budgets (user_email, total_epsilon, queries_count) 
                   VALUES (%s, %s, 1)
                   ON CONFLICT (user_email) DO UPDATE 
                   SET total_epsilon = privacy_budgets.total_epsilon + %s,
                       queries_count = privacy_budgets.queries_count + 1,
                       last_updated = CURRENT_TIMESTAMP""",
                (user_email, epsilon_used, epsilon_used)
            )

def get_user_files(user_email, limit=50):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, filename, original_filename, file_type, file_size, 
                          uploaded_at, processed 
                   FROM uploaded_files 
                   WHERE user_email = %s 
                   ORDER BY uploaded_at DESC LIMIT %s""",
                (user_email, limit)
            )
            return cur.fetchall()

def get_user_file_by_filename(user_email, filename):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, filename, original_filename, file_type, file_size,
                          uploaded_at, processed
                   FROM uploaded_files
                   WHERE user_email = %s AND filename = %s
                   ORDER BY uploaded_at DESC
                   LIMIT 1""",
                (user_email, filename)
            )
            return cur.fetchone()

def get_chat_history(user_email, limit=100):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT message, sender, created_at 
                   FROM chat_history 
                   WHERE user_email = %s 
                   ORDER BY created_at DESC LIMIT %s""",
                (user_email, limit)
            )
            return cur.fetchall()

def log_llm_privacy_audit(
    user_email, query, response, risk_score, risk_level,
    pii_count, synthetic_epsilon, cumulative_epsilon, sanitization_actions
):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO llm_privacy_logs 
                   (user_email, query_text, response_text, risk_score, risk_level,
                    pii_count, synthetic_epsilon, cumulative_epsilon, sanitization_actions)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (user_email, query[:500], response[:500], risk_score, risk_level,
                 pii_count, synthetic_epsilon, cumulative_epsilon,
                 json.dumps(sanitization_actions) if sanitization_actions else None)
            )

def get_llm_privacy_logs(user_email, limit=50):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT risk_score, risk_level, pii_count, synthetic_epsilon,
                          cumulative_epsilon, created_at
                   FROM llm_privacy_logs
                   WHERE user_email = %s
                   ORDER BY created_at DESC
                   LIMIT %s""",
                (user_email, limit)
            )
            return cur.fetchall()

def close_pool():
    global connection_pool
    if connection_pool:
        connection_pool.closeall()
