#secure_aggregation.py
def secure_mean(enc_weights_list):
    """
    Secure mean of encrypted model updates.
    No decryption happens here.
    """
    num_clients = len(enc_weights_list)
    aggregated = enc_weights_list[0]

    for client_weights in enc_weights_list[1:]:
        aggregated = [
            w1 + w2 for w1, w2 in zip(aggregated, client_weights)
        ]

    return [w * (1.0 / num_clients) for w in aggregated]