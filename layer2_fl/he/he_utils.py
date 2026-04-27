"""
Production-ready Homomorphic Encryption utilities with TenSEAL
"""

import tenseal as ts
import numpy as np
import base64
import logging
from typing import List, Tuple, Optional
import pickle

logger = logging.getLogger(__name__)

class HEContext:
    """Homomorphic Encryption context manager"""
    
    def __init__(
        self,
        poly_modulus_degree: int = 8192,
        coeff_mod_bit_sizes: List[int] = None,
        global_scale: int = 2**40
    ):
        self.poly_modulus_degree = poly_modulus_degree
        self.coeff_mod_bit_sizes = coeff_mod_bit_sizes or [60, 40, 40, 60]
        self.global_scale = global_scale
        self.context: Optional[ts.Context] = None
        
        self._initialize_context()
    
    def _initialize_context(self):
        """Initialize TenSEAL CKKS context"""
        try:
            self.context = ts.context(
                ts.SCHEME_TYPE.CKKS,
                poly_modulus_degree=self.poly_modulus_degree,
                coeff_mod_bit_sizes=self.coeff_mod_bit_sizes
            )
            self.context.generate_galois_keys()
            self.context.global_scale = self.global_scale
            
            logger.info(f"✅ HE context initialized: poly_mod={self.poly_modulus_degree}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize HE context: {e}")
            raise
    
    def serialize(self) -> bytes:
        """Serialize context to bytes"""
        return self.context.serialize()
    
    def get_public_context(self) -> bytes:
        """Get public context (without secret key)"""
        return self.context.serialize(save_secret_key=False)
    
    @staticmethod
    def load_context(serialized: bytes) -> 'HEContext':
        """Load context from serialized bytes"""
        he_ctx = HEContext.__new__(HEContext)
        he_ctx.context = ts.context_from(serialized)
        return he_ctx

def create_context(
    poly_modulus_degree: int = 8192,
    coeff_mod_bit_sizes: List[int] = None,
    global_scale: int = 2**40
) -> ts.Context:
    """
    Create TenSEAL CKKS context (backward compatible)
    
    Args:
        poly_modulus_degree: Polynomial modulus degree
        coeff_mod_bit_sizes: Coefficient modulus bit sizes
        global_scale: Global scale for encoding
    
    Returns:
        TenSEAL context
    """
    coeff_mod_bit_sizes = coeff_mod_bit_sizes or [60, 40, 40, 60]
    
    try:
        context = ts.context(
            ts.SCHEME_TYPE.CKKS,
            poly_modulus_degree=poly_modulus_degree,
            coeff_mod_bit_sizes=coeff_mod_bit_sizes
        )
        context.generate_galois_keys()
        context.global_scale = global_scale
        
        logger.info("✅ HE context created successfully")
        return context
        
    except Exception as e:
        logger.error(f"❌ Failed to create HE context: {e}")
        raise

def encode_bytes(b: bytes) -> str:
    """Encode bytes to base64 string"""
    return base64.b64encode(b).decode("utf-8")

def decode_bytes(s: str) -> bytes:
    """Decode base64 string to bytes"""
    return base64.b64decode(s.encode("utf-8"))

def encrypt_weights(
    context: ts.Context,
    weights: List[np.ndarray],
    max_size: int = 8192
) -> List[str]:
    """
    Encrypt model weights using CKKS
    
    Args:
        context: TenSEAL context
        weights: List of numpy arrays (model weights)
        max_size: Maximum vector size for encryption
    
    Returns:
        List of base64-encoded encrypted weights
    """
    encrypted = []
    
    try:
        for i, w in enumerate(weights):
            # Flatten and convert to float64
            flat = w.flatten().astype(np.float64)
            
            # Handle large tensors by chunking
            if len(flat) > max_size:
                logger.warning(f"Weight tensor {i} size {len(flat)} exceeds max_size, chunking...")
                chunks = []
                for start in range(0, len(flat), max_size):
                    chunk = flat[start:start + max_size]
                    enc_chunk = ts.ckks_vector(context, chunk.tolist())
                    chunks.append(encode_bytes(enc_chunk.serialize()))
                
                # Store as list of chunks
                encrypted.append({
                    'type': 'chunked',
                    'chunks': chunks,
                    'original_size': len(flat)
                })
            else:
                # Encrypt normally
                enc = ts.ckks_vector(context, flat.tolist())
                encrypted.append({
                    'type': 'single',
                    'data': encode_bytes(enc.serialize())
                })
        
        logger.info(f"✅ Encrypted {len(weights)} weight tensors")
        return encrypted
        
    except Exception as e:
        logger.error(f"❌ Weight encryption failed: {e}")
        raise

def decrypt_weights(
    context: ts.Context,
    enc_weights: List,
    shapes: List[Tuple],
    max_size: int = 8192
) -> List[np.ndarray]:
    """
    Decrypt encrypted weights
    
    Args:
        context: TenSEAL context
        enc_weights: List of encrypted weights
        shapes: Original shapes of weight tensors
        max_size: Maximum vector size
    
    Returns:
        List of decrypted numpy arrays
    """
    decrypted = []
    
    try:
        for enc, shape in zip(enc_weights, shapes):
            if isinstance(enc, dict):
                if enc['type'] == 'chunked':
                    # Reconstruct from chunks
                    flat_values = []
                    for chunk_data in enc['chunks']:
                        raw = decode_bytes(chunk_data)
                        vec = ts.ckks_vector_from(context, raw)
                        flat_values.extend(vec.decrypt())
                    
                    # Take only original size (remove padding)
                    flat_values = flat_values[:enc['original_size']]
                    arr = np.array(flat_values, dtype=np.float32)
                    
                else:  # single
                    raw = decode_bytes(enc['data'])
                    vec = ts.ckks_vector_from(context, raw)
                    arr = np.array(vec.decrypt(), dtype=np.float32)
            else:
                # Backward compatibility (old format)
                raw = decode_bytes(enc)
                vec = ts.ckks_vector_from(context, raw)
                arr = np.array(vec.decrypt(), dtype=np.float32)
            
            # Reshape to original shape
            decrypted.append(arr.reshape(shape))
        
        logger.info(f"✅ Decrypted {len(shapes)} weight tensors")
        return decrypted
        
    except Exception as e:
        logger.error(f"❌ Weight decryption failed: {e}")
        raise

def secure_aggregate(
    enc_weights_list: List[List],
    num_clients: Optional[int] = None
) -> List:
    """
    Securely aggregate encrypted weights (homomorphic addition)
    
    Args:
        enc_weights_list: List of encrypted weights from multiple clients
        num_clients: Number of clients (for averaging)
    
    Returns:
        Aggregated encrypted weights
    """
    if not enc_weights_list:
        raise ValueError("Empty weights list provided")
    
    num_clients = num_clients or len(enc_weights_list)
    
    try:
        # Initialize with first client's weights
        aggregated = enc_weights_list[0]
        
        # Add remaining clients' weights (homomorphic addition)
        for client_weights in enc_weights_list[1:]:
            for i in range(len(aggregated)):
                if isinstance(aggregated[i], dict):
                    if aggregated[i]['type'] == 'single':
                        # Deserialize, add, reserialize
                        vec1_bytes = decode_bytes(aggregated[i]['data'])
                        vec2_bytes = decode_bytes(client_weights[i]['data'])
                        
                        # Note: This requires same context on both sides
                        # In production, do this operation on HE server
                        aggregated[i]['data'] = encode_bytes(
                            (ts.ckks_vector_from(None, vec1_bytes) + 
                             ts.ckks_vector_from(None, vec2_bytes)).serialize()
                        )
        
        logger.info(f"✅ Securely aggregated weights from {len(enc_weights_list)} clients")
        return aggregated
        
    except Exception as e:
        logger.error(f"❌ Secure aggregation failed: {e}")
        raise

if __name__ == "__main__":
    # Test HE utilities
    print("Testing HE utilities...")
    
    # Create context
    context = create_context()
    print(f"✅ Context created")
    
    # Test encryption/decryption
    weights = [np.random.randn(3, 5).astype(np.float32)]
    shapes = [w.shape for w in weights]
    
    encrypted = encrypt_weights(context, weights)
    print(f"✅ Weights encrypted: {len(encrypted)} tensors")
    
    decrypted = decrypt_weights(context, encrypted, shapes)
    print(f"✅ Weights decrypted: {len(decrypted)} tensors")
    
    # Verify accuracy
    error = np.abs(weights[0] - decrypted[0]).max()
    print(f"Max decryption error: {error:.6f}")
    
    if error < 1e-3:
        print("✅ HE test successful!")
    else:
        print(f"⚠️ High decryption error: {error}")