#audit.py 
from db.postgres import get_connection
from datetime import datetime

def log_action(action: str, detail: str = None):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO audit_logs (action, details, created_at)
        VALUES (%s, %s, %s)
        """,
        (action, detail, datetime.utcnow())
    )

    conn.commit()
    cur.close()
    conn.close()