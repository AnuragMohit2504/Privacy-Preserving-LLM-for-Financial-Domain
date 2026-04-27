from he.he_utils import create_context, encrypt_weights
import numpy as np

ctx = create_context()

w = [np.array([1.0,2.0,3.0])]

enc = encrypt_weights(ctx, w)

print(enc)

from he.he_utils import decrypt_weights

shapes = [w[0].shape]

dec = decrypt_weights(ctx, enc, shapes)

print(dec)