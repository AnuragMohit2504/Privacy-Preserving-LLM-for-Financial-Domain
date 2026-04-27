"""
FL Bridge - Communication layer between Flask backend and FL Server
"""

import requests
import logging
import json

logger = logging.getLogger(__name__)

HE_SERVER_URL = "http://127.0.0.1:9000"
FL_SERVER_URL = "http://127.0.0.1:8000"
TIMEOUT = 10  # seconds

def encrypt_features(features_list):
    try:
        r = requests.post(
            f"{HE_SERVER_URL}/encrypt",
            json=features_list,
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            return r.json()["encrypted"]
        else:
            logger.error("HE encryption failed")
            return features_list
    except Exception as e:
        logger.error(f"HE encryption error: {e}")
        return features_list
def init_he_context():
    try:
        response = requests.post(
            f"{HE_SERVER_URL}/init_context",
            json={
                "poly_modulus_degree": 8192,
                "coeff_mod_bit_sizes": [60, 40, 40, 60]
            },
            timeout=TIMEOUT
        )

        if response.status_code == 200:
            logger.info("✅ HE context initialized")
            return True
        else:
            logger.error(f"HE init failed: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"HE init error: {e}")
        return False
def check_fl_status():
    """Check FL server status"""
    try:
        response = requests.get(
            f"{FL_SERVER_URL}/api/status",
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"FL status check failed: {response.status_code}")
            return {
                "status": "offline",
                "error": f"HTTP {response.status_code}"
            }
            
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to FL server - is it running?")
        return {
            "status": "offline",
            "error": "Connection refused"
        }
    except requests.exceptions.Timeout:
        logger.error("FL server timeout")
        return {
            "status": "offline",
            "error": "Timeout"
        }
    except Exception as e:
        logger.error(f"FL status check error: {str(e)}")
        return {
            "status": "offline",
            "error": str(e)
        }

def submit_features_for_training(feature_vector, features_dict):
    """Submit features to FL server for training"""
    try:
        # Convert numpy array to list if needed
        if hasattr(feature_vector, 'tolist'):
            features_list = feature_vector.tolist()
        else:
            features_list = list(feature_vector)

        payload = {
            "features": features_list,
            "metadata": features_dict
        }

        logger.info(f"Submitting {len(features_list)} features to FL server")

        response = requests.post(
            f"{FL_SERVER_URL}/api/submit_features",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT
        )

        logger.info(f"FL server response status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Features submitted successfully: {result}")
            return result
        else:
            logger.error(f"FL server returned status {response.status_code}")
            return {
                "status": "error",
                "message": f"FL server returned {response.status_code}"
            }

    except Exception as e:
        logger.error(f"Failed to submit features: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to submit features: {str(e)}"
        }

def get_model_insights():
    """Get insights from the trained model"""
    try:
        response = requests.get(
            f"{FL_SERVER_URL}/api/model_insights",
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "status": "error",
                "message": f"HTTP {response.status_code}"
            }
            
    except Exception as e:
        logger.error(f"Failed to get model insights: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }

def get_training_status():
    """Get current training status"""
    try:
        response = requests.get(
            f"{FL_SERVER_URL}/api/training_status",
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Training status check failed: {response.status_code}")
            return {
                "status": "unknown",
                "current_round": 0,
                "pending_features": 0,
                "active_clients": 0
            }
            
    except requests.exceptions.ConnectionError:
        return {
            "status": "offline",
            "current_round": 0,
            "pending_features": 0,
            "active_clients": 0
        }
    except Exception as e:
        logger.error(f"Failed to get training status: {str(e)}")
        return {
            "status": "error",
            "current_round": 0,
            "pending_features": 0,
            "active_clients": 0
        }

def trigger_fl_round():
    """Manually trigger a federated learning round"""
    try:
        logger.info("Triggering FL training round...")
        
        response = requests.post(
            f"{FL_SERVER_URL}/api/trigger_round",
            timeout=TIMEOUT
        )
        
        logger.info(f"Trigger response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Round triggered: {result}")
            return result
        else:
            error_msg = f"Failed to trigger round: HTTP {response.status_code}"
            logger.error(error_msg)
            return {
                "status": "error",
                "message": error_msg
            }
            
    except requests.exceptions.ConnectionError:
        error_msg = "Cannot connect to FL server"
        logger.error(error_msg)
        return {
            "status": "error",
            "message": error_msg
        }
    except Exception as e:
        error_msg = f"Failed to trigger round: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "error",
            "message": error_msg
        }

def submit_model_update(client_id, round_number, weights, metrics):
    """Submit model updates from client"""
    try:
        payload = {
            "client_id": client_id,
            "round_number": round_number,
            "weights": weights.tolist() if hasattr(weights, 'tolist') else weights,
            "metrics": metrics
        }
        
        response = requests.post(
            f"{FL_SERVER_URL}/api/submit_update",
            json=payload,
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "status": "error",
                "message": f"HTTP {response.status_code}"
            }
            
    except Exception as e:
        logger.error(f"Failed to submit update: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }

def get_aggregated_model():
    """Get aggregated model from server"""
    try:
        response = requests.get(
            f"{FL_SERVER_URL}/api/aggregate",
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "status": "error",
                "message": f"HTTP {response.status_code}"
            }
            
    except Exception as e:
        logger.error(f"Failed to get aggregated model: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }