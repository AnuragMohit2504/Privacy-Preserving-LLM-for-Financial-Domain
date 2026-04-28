#postgres.py

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "fingpt",
    "user": "postgres",
    "password": "admin",
}


def get_connection():
    return psycopg2.connect(
        **DB_CONFIG,
        cursor_factory=RealDictCursor
    )


# ==========================
# Audit Logs
# ==========================
def insert_audit_log(action: str, details: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_logs (action, details, created_at)
                VALUES (%s, %s, %s)
                """,
                (action, details, datetime.utcnow()),
            )
            conn.commit()
    finally:
        conn.close()


# ==========================
# Training Round Metadata
# ==========================
def log_training_round(client_id: str, round_no: int, epsilon: float, accuracy: float = None):
    """
    Store ONLY metadata:
    - client id
    - round number
    - privacy budget
    - optional model accuracy
    NO data, NO gradients, NO weights.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.columns WHERE table_name = 'training_rounds' AND column_name = 'accuracy'"
            )
            if cur.fetchone():
                cur.execute(
                    """
                    INSERT INTO training_rounds (
                        client_id,
                        round_no,
                        epsilon,
                        accuracy,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (client_id, round_no, float(epsilon), accuracy, datetime.utcnow()),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO training_rounds (
                        client_id,
                        round_no,
                        epsilon,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (client_id, round_no, float(epsilon), datetime.utcnow()),
                )
            conn.commit()
    finally:
        conn.close()
