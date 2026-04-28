"""
Production Homomorphic Encryption Server with TenSEAL CKKS
Provides real encryption/decryption and secure aggregation capabilities.
"""

import os
import time
import base64
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import numpy as np

# Try to import TenSEAL
try:
    import tenseal as ts
    TENSEAL_AVAILABLE = True
except ImportError:
    TENSEAL_AVAILABLE = False
    logging.warning("TenSEAL not available. HE server will run in MOCK mode.")

app = FastAPI(title="FINGPT HE Server")
logger = logging.getLogger(__name__)

# Global HE state
he_context = None
he_public_context = None
encrypted_storage: List[Dict] = []

# Performance metrics
encryption_times = []
decryption_times = []
aggregation_times = []
ciphertext_sizes = []


class HEContextRequest(BaseModel):
    poly_modulus_degree: int = 8192
    coeff_mod_bit_sizes: List[int] = [60, 40, 40, 60]
    global_scale: int = 40  # 2^40


class EncryptRequest(BaseModel):
    features: List[float]
    chunk_size: Optional[int] = 4096


class DecryptRequest(BaseModel):
    ciphertext: str  # base64 encoded
    shape: Optional[List[int]] = None


class AggregateRequest(BaseModel):
    ciphertexts: List[str]  # base64 encoded ciphertexts


@dataclass
class HEMetrics:
    encryption_time_ms: float = 0.0
    decryption_time_ms: float = 0.0
    aggregation_time_ms: float = 0.0
    ciphertext_size_bytes: int = 0
    ciphertext_expansion_ratio: float = 0.0
    accuracy_loss: float = 0.0


def create_he_context(req: HEContextRequest) -> Optional[Any]:
    """Create TenSEAL CKKS context."""
    if not TENSEAL_AVAILABLE:
        return None
    
    try:
        context = ts.context(
            ts.SCHEME_TYPE.CKKS,
            poly_modulus_degree=req.poly_modulus_degree,
            coeff_mod_bit_sizes=req.coeff_mod_bit_sizes
        )
        context.generate_galois_keys()
        context.global_scale = 2 ** req.global_scale
        return context
    except Exception as e:
        logger.error(f"Failed to create HE context: {e}")
        return None


@app.post("/init_context")
async def init_context(req: HEContextRequest = None):
    """Initialize HE context."""
    global he_context, he_public_context
    
    if req is None:
        req = HEContextRequest()
    
    if not TENSEAL_AVAILABLE:
        logger.warning("Running in MOCK mode - TenSEAL not installed")
        return {
            "status": "mock",
            "message": "HE context initialized in MOCK mode (TenSEAL not available)",
            "context": {
                "poly_modulus_degree": req.poly_modulus_degree,
                "coeff_mod_bit_sizes": req.coeff_mod_bit_sizes,
                "mode": "mock"
            }
        }
    
    he_context = create_he_context(req)
    if he_context is None:
        raise HTTPException(status_code=500, detail="Failed to create HE context")
    
    # Serialize public context (no secret key)
    he_public_context = base64.b64encode(
        he_context.serialize(save_secret_key=False)
    ).decode("utf-8")
    
    logger.info(f"HE context initialized: poly_mod={req.poly_modulus_degree}")
    
    return {
        "status": "success",
        "message": "HE context initialized",
        "public_context": he_public_context[:100] + "...",
        "context": {
            "poly_modulus_degree": req.poly_modulus_degree,
            "coeff_mod_bit_sizes": req.coeff_mod_bit_sizes,
            "global_scale": req.global_scale,
            "mode": "production"
        }
    }


@app.post("/encrypt")
async def encrypt(data: EncryptRequest):
    """Encrypt feature vector using CKKS."""
    global he_context
    
    if he_context is None:
        # Auto-initialize
        await init_context()
    
    features = data.features
    if not features:
        raise HTTPException(status_code=400, detail="Features cannot be empty")
    
    start_time = time.time()
    
    if not TENSEAL_AVAILABLE or he_context is None:
        # MOCK mode: simple obfuscation
        encrypted = [f * 2 + 1 for f in features]
        elapsed = (time.time() - start_time) * 1000
        
        return {
            "status": "mock",
            "encrypted": encrypted,
            "encryption_time_ms": elapsed,
            "mode": "mock",
            "message": "Mock encryption (TenSEAL not available)"
        }
    
    # Real TenSEAL encryption
    try:
        # Convert to numpy and chunk if needed
        features_np = np.array(features, dtype=np.float64)
        chunk_size = data.chunk_size or 4096
        
        encrypted_chunks = []
        for i in range(0, len(features_np), chunk_size):
            chunk = features_np[i:i + chunk_size]
            ckks_vector = ts.ckks_vector(he_context, chunk.tolist())
            serialized = base64.b64encode(ckks_vector.serialize()).decode("utf-8")
            encrypted_chunks.append(serialized)
        
        elapsed = (time.time() - start_time) * 1000
        encryption_times.append(elapsed)
        
        # Calculate ciphertext size
        total_size = sum(len(chunk) for chunk in encrypted_chunks)
        ciphertext_sizes.append(total_size)
        
        # Calculate expansion ratio
        original_size = len(features) * 8  # 8 bytes per float64
        expansion = total_size / original_size if original_size > 0 else 0
        
        return {
            "status": "success",
            "encrypted_chunks": encrypted_chunks,
            "num_chunks": len(encrypted_chunks),
            "encryption_time_ms": round(elapsed, 2),
            "ciphertext_size_bytes": total_size,
            "expansion_ratio": round(expansion, 2),
            "original_size_bytes": original_size
        }
        
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise HTTPException(status_code=500, detail=f"Encryption failed: {str(e)}")


@app.post("/decrypt")
async def decrypt(data: DecryptRequest):
    """Decrypt ciphertext."""
    global he_context
    
    if he_context is None:
        raise HTTPException(status_code=400, detail="HE context not initialized")
    
    if not TENSEAL_AVAILABLE:
        return {
            "status": "mock",
            "decrypted": [],
            "message": "Mock decryption (TenSEAL not available)"
        }
    
    start_time = time.time()
    
    try:
        ciphertext_bytes = base64.b64decode(data.ciphertext)
        ckks_vector = ts.ckks_vector_from(he_context, ciphertext_bytes)
        decrypted = ckks_vector.decrypt()
        
        elapsed = (time.time() - start_time) * 1000
        decryption_times.append(elapsed)
        
        return {
            "status": "success",
            "decrypted": decrypted,
            "decryption_time_ms": round(elapsed, 2)
        }
        
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise HTTPException(status_code=500, detail=f"Decryption failed: {str(e)}")


@app.post("/aggregate")
async def aggregate(data: AggregateRequest):
    """Homomorphically aggregate encrypted vectors."""
    global he_context
    
    if he_context is None:
        raise HTTPException(status_code=400, detail="HE context not initialized")
    
    ciphertexts = data.ciphertexts
    if len(ciphertexts) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 ciphertexts to aggregate")
    
    start_time = time.time()
    
    if not TENSEAL_AVAILABLE:
        # MOCK: average the mock encrypted values
        return {
            "status": "mock",
            "message": "Mock aggregation (TenSEAL not available)",
            "num_inputs": len(ciphertexts)
        }
    
    try:
        # Deserialize first ciphertext
        first_bytes = base64.b64decode(ciphertexts[0])
        aggregated = ts.ckks_vector_from(he_context, first_bytes)
        
        # Add remaining ciphertexts (homomorphic addition)
        for ct_str in ciphertexts[1:]:
            ct_bytes = base64.b64decode(ct_str)
            ct_vector = ts.ckks_vector_from(he_context, ct_bytes)
            aggregated = aggregated + ct_vector
        
        # Average by multiplying with 1/n
        n = len(ciphertexts)
        aggregated = aggregated * (1.0 / n)
        
        elapsed = (time.time() - start_time) * 1000
        aggregation_times.append(elapsed)
        
        # Serialize result
        result_serialized = base64.b64encode(aggregated.serialize()).decode("utf-8")
        
        return {
            "status": "success",
            "aggregated": result_serialized,
            "num_inputs": n,
            "aggregation_time_ms": round(elapsed, 2)
        }
        
    except Exception as e:
        logger.error(f"Aggregation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Aggregation failed: {str(e)}")


@app.get("/metrics")
async def get_metrics():
    """Get HE performance metrics."""
    metrics = {
        "status": "production" if TENSEAL_AVAILABLE else "mock",
        "tenseal_available": TENSEAL_AVAILABLE,
        "context_initialized": he_context is not None,
        "encryption": {
            "count": len(encryption_times),
            "avg_time_ms": round(np.mean(encryption_times), 2) if encryption_times else 0,
            "min_time_ms": round(np.min(encryption_times), 2) if encryption_times else 0,
            "max_time_ms": round(np.max(encryption_times), 2) if encryption_times else 0,
        },
        "decryption": {
            "count": len(decryption_times),
            "avg_time_ms": round(np.mean(decryption_times), 2) if decryption_times else 0,
            "min_time_ms": round(np.min(decryption_times), 2) if decryption_times else 0,
            "max_time_ms": round(np.max(decryption_times), 2) if decryption_times else 0,
        },
        "aggregation": {
            "count": len(aggregation_times),
            "avg_time_ms": round(np.mean(aggregation_times), 2) if aggregation_times else 0,
            "min_time_ms": round(np.min(aggregation_times), 2) if aggregation_times else 0,
            "max_time_ms": round(np.max(aggregation_times), 2) if aggregation_times else 0,
        },
        "ciphertext": {
            "count": len(ciphertext_sizes),
            "avg_size_bytes": round(np.mean(ciphertext_sizes), 0) if ciphertext_sizes else 0,
            "avg_expansion_ratio": round(
                np.mean([s / (i+1) for i, s in enumerate(ciphertext_sizes)]), 2
            ) if ciphertext_sizes else 0
        }
    }
    
    return metrics


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "tenseal_available": TENSEAL_AVAILABLE,
        "context_ready": he_context is not None
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("="*60)
    print("FINGPT Homomorphic Encryption Server")
    print("="*60)
    print(f"TenSEAL available: {TENSEAL_AVAILABLE}")
    print(f"Mode: {'PRODUCTION' if TENSEAL_AVAILABLE else 'MOCK'}")
    print("="*60)
    
    uvicorn.run(app, host="127.0.0.1", port=9000, log_level="info")

