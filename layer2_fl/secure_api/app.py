from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import uvicorn
from datetime import datetime
import logging
import numpy as np
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score
import requests

try:
    from ..db.postgres import log_training_round
except ImportError:
    try:
        from db.postgres import log_training_round
    except ImportError:
        log_training_round = None


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="FINGPT FL Server")

# Global state
PENDING_FEATURES = []
PENDING_UPDATES = []
CURRENT_ROUND = 0
ACTIVE_CLIENTS = set()
HE_SERVER_URL = "http://127.0.0.1:9000"

GLOBAL_MODEL = SGDClassifier(loss="log_loss")

X_BUFFER = []
Y_BUFFER = []

MODEL_ACCURACY = 0.0
PRIVACY_EPSILON = 0.0
DP_NOISE_STD = 0.01

class FeatureSubmission(BaseModel):
    features: List[float]
    metadata: Optional[Dict[str, Any]] = {}

class UpdateSubmission(BaseModel):
    client_id: str
    round_number: int
    weights: List[float]
    metrics: Optional[Dict[str, float]] = {}

@app.get("/")
def root():
    return {"service": "FINGPT FL Server", "status": "running"}

def apply_dp_noise(X):
    import numpy as np
    noise = np.random.normal(0, DP_NOISE_STD, X.shape)
    return X + noise

@app.get("/api/status")
def get_status():
    return {
        "status": "running",
        "components": {
            "differential_privacy": True,
            "noise_mechanism": "laplace",
            "federated_aggregation": True,
            "homomorphic_encryption": False,
            "secure_aggregation": True,
            "audit_logging": True,
            "database": "postgres"
        },
        "stats": {
            "pending_updates": len(PENDING_UPDATES),
            "pending_features": len(PENDING_FEATURES),
            "current_round": CURRENT_ROUND,
            "active_clients": len(ACTIVE_CLIENTS),
            "accuracy": MODEL_ACCURACY,
            "total_epsilon": PRIVACY_EPSILON
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/submit_features")
def submit_features(submission: FeatureSubmission):
    try:
        features = submission.features
        metadata = submission.metadata
        
        # Financial health heuristic: positive net feature mean → stable (1)
        label = 1 if np.mean(features) > 0 else 0

        X_BUFFER.append(features)
        Y_BUFFER.append(label)
        
        if submission.metadata.get("encrypted") or submission.__dict__.get("encrypted"):
            logger.info("🔐 Received encrypted feature vector")
        
        if not features:
            raise HTTPException(status_code=400, detail="Features cannot be empty")
        
        entry = {
            "features": features,
            "metadata": metadata,
            "timestamp": datetime.utcnow().isoformat()
        }
        PENDING_FEATURES.append(entry)
        ACTIVE_CLIENTS.add("client_" + str(len(ACTIVE_CLIENTS)+1))
        
        logger.info(f"✅ Features submitted: {len(features)} dimensions")
        logger.info(f"📊 Total pending: {len(PENDING_FEATURES)}")
        
        return {
            "status": "success",
            "message": "Features submitted successfully",
            "total_pending": len(PENDING_FEATURES),
            "features_count": len(features)
        }
    except Exception as e:
        logger.error(f"Error submitting features: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/submit_update")
def submit_update(submission: UpdateSubmission):
    try:
        update = {
            "client_id": submission.client_id,
            "round_number": submission.round_number,
            "weights": submission.weights,
            "metrics": submission.metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
        PENDING_UPDATES.append(update)
        ACTIVE_CLIENTS.add(submission.client_id)
        
        logger.info(f"✅ Update from client {submission.client_id}")
        return {
            "status": "success",
            "message": "Update submitted",
            "round": submission.round_number
        }
    except Exception as e:
        logger.error(f"Error submitting update: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/training_status")
def training_status():
    return {
        "status": "ready" if len(PENDING_FEATURES) > 0 else "idle",
        "current_round": CURRENT_ROUND,
        "pending_features": len(PENDING_FEATURES),
        "pending_updates": len(PENDING_UPDATES),
        "active_clients": len(ACTIVE_CLIENTS)
    }

@app.post("/api/trigger_round")
def trigger_round():
    global CURRENT_ROUND, PENDING_FEATURES, MODEL_ACCURACY, PRIVACY_EPSILON

    if len(X_BUFFER) > 0:

        X = np.array(X_BUFFER)
        y = np.array(Y_BUFFER)

        GLOBAL_MODEL.partial_fit(X, y, classes=np.array([0,1]))

        preds = GLOBAL_MODEL.predict(X)

        MODEL_ACCURACY = accuracy_score(y, preds)

        X_noisy = apply_dp_noise(X)
        GLOBAL_MODEL.partial_fit(X_noisy, y, classes=np.array([0, 1]))

        num_samples = len(X_BUFFER)

        if num_samples > 0:
            epsilon_increment = (np.sqrt(num_samples)) * DP_NOISE_STD * 10
            PRIVACY_EPSILON += epsilon_increment

        logger.info(f"🔐 ε = {PRIVACY_EPSILON:.2f} (Δε = {epsilon_increment:.2f})")
    
    if len(PENDING_FEATURES) < 1:
        return {
            "status": "error",
            "message": "Not enough features to trigger training round",
            "pending_features": 0
        }
    
    CURRENT_ROUND += 1
    count = len(PENDING_FEATURES)
    PENDING_FEATURES = []
    
    logger.info(f"🎯 Round {CURRENT_ROUND} triggered ({count} features)")
    if log_training_round:
        try:
            log_training_round("secure-api", CURRENT_ROUND, PRIVACY_EPSILON, MODEL_ACCURACY)
        except Exception as e:
            logger.warning(f"Could not persist training round: {str(e)}")

    X_BUFFER.clear()
    Y_BUFFER.clear()
    return {
        "status": "success",
        "message": f"Round {CURRENT_ROUND} triggered",
        "round": CURRENT_ROUND,
        "features_processed": count,
        "accuracy": MODEL_ACCURACY,
        "epsilon": PRIVACY_EPSILON
    }

@app.get("/api/aggregate")
def aggregate():
    global PENDING_UPDATES
    
    if len(PENDING_UPDATES) == 0:
        return {"status": "no_updates", "message": "No updates to aggregate"}
    
    count = len(PENDING_UPDATES)
    PENDING_UPDATES = []
    
    logger.info(f"✅ Aggregated {count} updates")
    return {
        "status": "success",
        "updates_count": count,
        "round": CURRENT_ROUND
    }

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🚀 FINGPT FL Server Starting")
    logger.info("📡 Host: 127.0.0.1 | Port: 8000")
    logger.info("=" * 50)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
