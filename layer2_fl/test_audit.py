from db.audit import log_action

if __name__ == "__main__":
    log_action("SYSTEM_BOOT", "Layer2 backend initialized")
    print("✅ Audit log inserted")
