from fastapi import FastAPI
from pydantic import BaseModel
import logging

app = FastAPI()
logger = logging.getLogger(__name__)

# ✅ Request model (OPTIONAL now)
class HEContextRequest(BaseModel):
    poly_modulus_degree: int = 8192
    coeff_mod_bit_sizes: list[int] = [60, 40, 40, 60]

he_context = None

@app.post("/init_context")
async def init_context(req: HEContextRequest = None):
    global he_context
    
    try:
        # Use default if request is empty
        if req is None:
            req = HEContextRequest()
        
        he_context = {
            "poly_modulus_degree": req.poly_modulus_degree,
            "coeff_mod_bit_sizes": req.coeff_mod_bit_sizes
        }

        logger.info(f"HE Context initialized: {he_context}")

        return {
            "status": "success",
            "message": "HE context initialized",
            "context": he_context
        }

    except Exception as e:
        logger.error(f"HE init error: {str(e)}")
        return {"status": "error", "message": str(e)}


@app.post("/encrypt")
async def encrypt(data: dict):
    try:
        features = data.get("features", [])

        # Dummy encryption (you can replace with TenSEAL later)
        encrypted = [f * 2 for f in features]

        return {"encrypted": encrypted}

    except Exception as e:
        return {"error": str(e)}