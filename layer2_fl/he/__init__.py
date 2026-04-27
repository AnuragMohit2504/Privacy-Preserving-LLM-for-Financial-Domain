import tenseal as ts
import numpy as np

def create_context():
    """
    CKKS context for homomorphic encryption.
    Enables encrypted addition & scaling.
    """
    ctx = ts.context(
        ts.SCHEME_TYPE.CKKS,
        poly_modulus_degree=8192,
        coeff_mod_bit_sizes=[60, 40, 40, 60],
    )
    ctx.global_scale = 2 ** 40
    ctx.generate_galois_keys()
    return ctx

def encrypt_vector(ctx, vector: np.ndarray):
    return ts.ckks_vector(ctx, vector.tolist())

def decrypt_vector(enc_vector):
    return np.array(enc_vector.decrypt())
