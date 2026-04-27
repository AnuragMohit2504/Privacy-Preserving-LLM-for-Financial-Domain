from db.postgres import get_connection

def test_connection():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT NOW();")
    result = cur.fetchone()
    print("✅ Connected to DB:", result)
    cur.close()
    conn.close()

if __name__ == "__main__":
    test_connection()
