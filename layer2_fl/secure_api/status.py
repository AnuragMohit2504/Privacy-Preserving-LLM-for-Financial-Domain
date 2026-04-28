from fastapi import APIRouter
try:
    from ..db.postgres import get_connection
except ImportError:
    from db.postgres import get_connection

router = APIRouter()

@router.get("/status")
def system_status():
    return {
        "status": "running",
        "components": {
            "federated_learning": True,
            "differential_privacy": True,
            "homomorphic_encryption": True,
            "audit_logging": True
        }
    }

@router.get("/training-rounds")
def training_rounds():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT client_id, round_no, epsilon, created_at
            FROM training_rounds
            ORDER BY created_at DESC
            LIMIT 50
        """)
        rows = cur.fetchall()
    return rows
