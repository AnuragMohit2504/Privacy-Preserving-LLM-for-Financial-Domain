#aggregator.py

import tenseal as ts
import requests


# Server holds ONLY public context (no secret key)
SERVER_CONTEXT = None
ENCRYPTED_UPDATES = []
HE_SERVER = "http://127.0.0.1:9000"

def decrypt_vector(enc_data):
    r = requests.post(
        f"{HE_SERVER}/decrypt",
        json=enc_data
    )
    return r.json()["decrypted"]

def init_context(serialized_context: bytes):
    global SERVER_CONTEXT
    SERVER_CONTEXT = ts.context_from(serialized_context)
    SERVER_CONTEXT.make_context_public()


def add_encrypted_update(enc_weights):
    ENCRYPTED_UPDATES.append(enc_weights)


def aggregate_encrypted_updates():
    if not ENCRYPTED_UPDATES:
        return None

    num_clients = len(ENCRYPTED_UPDATES)
    aggregated = ENCRYPTED_UPDATES[0]

    for client_weights in ENCRYPTED_UPDATES[1:]:
        aggregated = [
            w1 + w2 for w1, w2 in zip(aggregated, client_weights)
        ]

    aggregated = [w * (1.0 / num_clients) for w in aggregated]
    aggregated = decrypt_vector(aggregated)

    ENCRYPTED_UPDATES.clear()
    return aggregated
