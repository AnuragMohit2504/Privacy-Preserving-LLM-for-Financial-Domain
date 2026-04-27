from opacus import PrivacyEngine
from opacus.validators import ModuleValidator
import torch.optim as optim


def make_private(model, optimizer, dataloader, noise, max_norm):

    # Fix unsupported layers (BatchNorm → GroupNorm)
    model = ModuleValidator.fix(model)

    # Recreate optimizer with new model parameters
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    privacy_engine = PrivacyEngine(secure_mode=False)

    model, optimizer, dataloader = privacy_engine.make_private(
        module=model,
        optimizer=optimizer,
        data_loader=dataloader,
        noise_multiplier=noise,
        max_grad_norm=max_norm,
    )

    return model, optimizer, dataloader, privacy_engine
#he_utils.py


# import tenseal as ts
# import numpy as np
# import base64

# def create_context():
#     context = ts.context(
#         ts.SCHEME_TYPE.CKKS,
#         poly_modulus_degree=8192,
#         coeff_mod_bit_sizes=[60, 40, 40, 60],
#     )
#     context.generate_galois_keys()
#     context.global_scale = 2**40
#     return context


# def encode_bytes(b: bytes) -> str:
#     return base64.b64encode(b).decode("utf-8")


# def decode_bytes(s: str) -> bytes:
#     return base64.b64decode(s.encode("utf-8"))


# def encrypt_weights(context, weights):
#     encrypted = []
#     for w in weights:
#         flat = w.flatten().astype(np.float64)
#         enc = ts.ckks_vector(context, flat)
#         encrypted.append(encode_bytes(enc.serialize()))
#     return encrypted


# def decrypt_weights(context, enc_weights, shapes):
#     decrypted = []
#     for enc, shape in zip(enc_weights, shapes):
#         raw = decode_bytes(enc)
#         vec = ts.ckks_vector_from(context, raw)
#         arr = np.array(vec.decrypt())
#         decrypted.append(arr.reshape(shape))
#     return decrypted