# server.py

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import flwr as fl
from fl_config import FLConfig
from db.audit import log_action

def start_server():
    # Log system startup
    log_action("SYSTEM_BOOT", "Layer2 backend initialized")
    print("✅ Audit log inserted")

    # Flower coordinator
    fl.server.start_server(
        server_address="127.0.0.1:8081",
        config=fl.server.ServerConfig(num_rounds=FLConfig.ROUNDS),
    )

if __name__ == "__main__":
    start_server()
