"""
Homomorphic Encryption Performance Evaluator
Measures encryption overhead, accuracy loss, and provides recommendations.
"""

import os
import sys
import time
import json
import logging
import argparse
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict

import numpy as np
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HE_SERVER_URL = "http://127.0.0.1:9000"


@dataclass
class HEEvaluationResult:
    """HE evaluation results container."""
    # Performance metrics
    encryption_time_ms: float = 0.0
    decryption_time_ms: float = 0.0
    aggregation_time_ms: float = 0.0
    total_roundtrip_ms: float = 0.0
    
    # Size metrics
    original_size_bytes: int = 0
    ciphertext_size_bytes: int = 0
    expansion_ratio: float = 0.0
    
    # Accuracy metrics
    original_values: List[float] = None
    decrypted_values: List[float] = None
    max_error: float = 0.0
    mean_error: float = 0.0
    rmse: float = 0.0
    snr_db: float = 0.0
    
    # Recommendations
    is_viable: bool = True
    recommendations: List[str] = None
    
    def __post_init__(self):
        if self.original_values is None:
            self.original_values = []
        if self.decrypted_values is None:
            self.decrypted_values = []
        if self.recommendations is None:
            self.recommendations = []
    
    def to_dict(self):
        return asdict(self)


def check_he_server() -> bool:
    """Check if HE server is running."""
    try:
        r = requests.get(f"{HE_SERVER_URL}/health", timeout=5)
        return r.status_code == 200
    except:
        return False


def evaluate_encryption_overhead(
    vector_sizes: List[int] = [100, 500, 1000, 4096, 8192],
    num_trials: int = 3
) -> Dict:
    """
    Evaluate encryption overhead for different vector sizes.
    
    Returns:
        Dictionary with performance data for each vector size.
    """
    results = {}
    
    for size in vector_sizes:
        logger.info(f"Testing vector size: {size}")
        
        # Generate random data
        data = np.random.randn(size).astype(np.float64).tolist()
        
        trial_results = []
        for trial in range(num_trials):
            # Encrypt
            start = time.time()
            r = requests.post(
                f"{HE_SERVER_URL}/encrypt",
                json={"features": data, "chunk_size": 4096},
                timeout=30
            )
            encrypt_time = (time.time() - start) * 1000
            
            if r.status_code != 200:
                logger.error(f"Encryption failed: {r.text}")
                continue
            
            result = r.json()
            
            trial_results.append({
                "encryption_time_ms": result.get("encryption_time_ms", encrypt_time),
                "ciphertext_size_bytes": result.get("ciphertext_size_bytes", 0),
                "expansion_ratio": result.get("expansion_ratio", 0),
                "original_size_bytes": result.get("original_size_bytes", size * 8)
            })
        
        if trial_results:
            results[size] = {
                "avg_encryption_time_ms": np.mean([t["encryption_time_ms"] for t in trial_results]),
                "avg_ciphertext_size_bytes": np.mean([t["ciphertext_size_bytes"] for t in trial_results]),
                "avg_expansion_ratio": np.mean([t["expansion_ratio"] for t in trial_results]),
                "trials": trial_results
            }
    
    return results


def evaluate_accuracy_loss(
    vector_size: int = 1000,
    num_trials: int = 5
) -> HEEvaluationResult:
    """
    Evaluate accuracy loss after encryption -> aggregation -> decryption.
    
    Returns:
        HEEvaluationResult with accuracy metrics.
    """
    result = HEEvaluationResult()
    
    # Generate test data
    original = np.random.randn(vector_size).astype(np.float64)
    result.original_values = original.tolist()
    result.original_size_bytes = vector_size * 8
    
    # Encrypt
    start = time.time()
    r = requests.post(
        f"{HE_SERVER_URL}/encrypt",
        json={"features": original.tolist(), "chunk_size": 4096},
        timeout=30
    )
    encrypt_time = (time.time() - start) * 1000
    
    if r.status_code != 200:
        logger.error(f"Encryption failed: {r.text}")
        result.is_viable = False
        result.recommendations.append("Encryption endpoint failed - check HE server")
        return result
    
    enc_result = r.json()
    result.encryption_time_ms = enc_result.get("encryption_time_ms", encrypt_time)
    result.ciphertext_size_bytes = enc_result.get("ciphertext_size_bytes", 0)
    result.expansion_ratio = enc_result.get("expansion_ratio", 0)
    
    # If mock mode, simulate decryption
    if enc_result.get("status") == "mock":
        logger.warning("HE server in MOCK mode - simulating accuracy")
        # Mock: values are f * 2 + 1, so reverse: (v - 1) / 2
        mock_decrypted = [(v - 1) / 2.0 for v in enc_result["encrypted"]]
        result.decrypted_values = mock_decrypted[:vector_size]
        result.decryption_time_ms = 0.1
    else:
        # Decrypt first chunk
        chunks = enc_result.get("encrypted_chunks", [])
        if chunks:
            start = time.time()
            r = requests.post(
                f"{HE_SERVER_URL}/decrypt",
                json={"ciphertext": chunks[0]},
                timeout=30
            )
            decrypt_time = (time.time() - start) * 1000
            
            if r.status_code == 200:
                dec_result = r.json()
                result.decryption_time_ms = dec_result.get("decryption_time_ms", decrypt_time)
                result.decrypted_values = dec_result.get("decrypted", [])[:vector_size]
    
    # Calculate accuracy metrics
    if result.decrypted_values and len(result.decrypted_values) == len(result.original_values):
        orig = np.array(result.original_values)
        dec = np.array(result.decrypted_values)
        
        diff = np.abs(orig - dec)
        result.max_error = float(np.max(diff))
        result.mean_error = float(np.mean(diff))
        result.rmse = float(np.sqrt(np.mean((orig - dec) ** 2)))
        
        # Signal-to-noise ratio
        signal_power = np.mean(orig ** 2)
        noise_power = np.mean((orig - dec) ** 2)
        if noise_power > 0:
            result.snr_db = float(10 * np.log10(signal_power / noise_power))
        else:
            result.snr_db = float('inf')
    
    result.total_roundtrip_ms = result.encryption_time_ms + result.decryption_time_ms
    
    # Generate recommendations
    result.recommendations = generate_recommendations(result)
    result.is_viable = result.max_error < 0.1 and result.expansion_ratio < 100
    
    return result


def evaluate_aggregation(
    num_clients: int = 3,
    vector_size: int = 1000
) -> Dict:
    """Evaluate secure aggregation performance."""
    # Generate data for multiple clients
    client_data = [np.random.randn(vector_size).astype(np.float64).tolist() 
                   for _ in range(num_clients)]
    
    # Encrypt all
    encrypted_chunks = []
    encrypt_times = []
    
    for data in client_data:
        r = requests.post(
            f"{HE_SERVER_URL}/encrypt",
            json={"features": data, "chunk_size": 4096},
            timeout=30
        )
        if r.status_code == 200:
            result = r.json()
            encrypt_times.append(result.get("encryption_time_ms", 0))
            if result.get("status") == "mock":
                encrypted_chunks.append(result["encrypted"])
            else:
                encrypted_chunks.extend(result.get("encrypted_chunks", []))
    
    # Aggregate
    start = time.time()
    if encrypted_chunks and isinstance(encrypted_chunks[0], str):
        # Real HE mode
        r = requests.post(
            f"{HE_SERVER_URL}/aggregate",
            json={"ciphertexts": encrypted_chunks[:num_clients]},
            timeout=30
        )
    else:
        # Mock mode - can't really aggregate mock values
        r = requests.post(
            f"{HE_SERVER_URL}/aggregate",
            json={"ciphertexts": ["mock1", "mock2"]},
            timeout=30
        )
    
    agg_time = (time.time() - start) * 1000
    
    return {
        "num_clients": num_clients,
        "vector_size": vector_size,
        "avg_encrypt_time_ms": np.mean(encrypt_times) if encrypt_times else 0,
        "aggregation_time_ms": r.json().get("aggregation_time_ms", agg_time) if r.status_code == 200 else agg_time,
        "status": "success" if r.status_code == 200 else "failed"
    }


def generate_recommendations(result: HEEvaluationResult) -> List[str]:
    """Generate recommendations based on evaluation results."""
    recommendations = []
    
    # Performance recommendations
    if result.encryption_time_ms > 1000:
        recommendations.append(
            f"Encryption is slow ({result.encryption_time_ms:.0f}ms). "
            "Consider reducing vector size or using batching."
        )
    
    if result.expansion_ratio > 50:
        recommendations.append(
            f"High ciphertext expansion ({result.expansion_ratio:.1f}x). "
            "Network bandwidth may be a bottleneck."
        )
    
    # Accuracy recommendations
    if result.max_error > 0.01:
        recommendations.append(
            f"Significant accuracy loss detected (max error: {result.max_error:.6f}). "
            "Consider increasing coeff_mod_bit_sizes or reducing poly_modulus_degree."
        )
    
    if result.snr_db < 40 and result.snr_db > 0:
        recommendations.append(
            f"Low SNR ({result.snr_db:.1f} dB). "
            "Encryption noise may affect model training."
        )
    
    # Viability
    if result.is_viable:
        recommendations.append("HE configuration is viable for production use.")
    else:
        recommendations.append("HE configuration NOT recommended. Consider alternatives.")
    
    # General recommendation about HE necessity
    recommendations.append(
        "HE is necessary only if: (1) server is untrusted, "
        "(2) regulatory requirements mandate it, or (3) aggregating in cloud. "
        "For trusted on-premise servers, Differential Privacy + TLS may suffice."
    )
    
    return recommendations


def run_full_evaluation(output_file: str = "he_evaluation_report.json") -> Dict:
    """Run complete HE evaluation and generate report."""
    logger.info("="*60)
    logger.info("HOMOMORPHIC ENCRYPTION EVALUATION")
    logger.info("="*60)
    
    # Check server
    if not check_he_server():
        logger.error("HE server not running. Start it with: python he_server.py")
        return {"error": "HE server not available"}
    
    # Get server info
    r = requests.get(f"{HE_SERVER_URL}/health")
    server_info = r.json()
    logger.info(f"Server mode: {'PRODUCTION' if server_info.get('tenseal_available') else 'MOCK'}")
    
    # 1. Encryption overhead evaluation
    logger.info("\n[1/3] Evaluating encryption overhead...")
    overhead_results = evaluate_encryption_overhead()
    
    # 2. Accuracy evaluation
    logger.info("\n[2/3] Evaluating accuracy loss...")
    accuracy_result = evaluate_accuracy_loss()
    
    # 3. Aggregation evaluation
    logger.info("\n[3/3] Evaluating secure aggregation...")
    agg_result = evaluate_aggregation()
    
    # Compile report
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "server_info": server_info,
        "encryption_overhead": overhead_results,
        "accuracy": accuracy_result.to_dict(),
        "aggregation": agg_result,
        "summary": {
            "mode": "production" if server_info.get("tenseal_available") else "mock",
            "encryption_viable": accuracy_result.is_viable,
            "avg_expansion_ratio": np.mean([
                v["avg_expansion_ratio"] 
                for v in overhead_results.values() 
                if isinstance(v, dict) and "avg_expansion_ratio" in v
            ]) if overhead_results else 0,
            "max_error": accuracy_result.max_error,
            "avg_encryption_time_ms": np.mean([
                v["avg_encryption_time_ms"] 
                for v in overhead_results.values() 
                if isinstance(v, dict) and "avg_encryption_time_ms" in v
            ]) if overhead_results else 0,
        },
        "recommendations": accuracy_result.recommendations
    }
    
    # Save report
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    print_summary(report)
    
    logger.info(f"\nReport saved to: {output_file}")
    return report


def print_summary(report: Dict):
    """Print evaluation summary."""
    print("\n" + "="*60)
    print("HE EVALUATION SUMMARY")
    print("="*60)
    
    summary = report.get("summary", {})
    print(f"\nMode: {summary.get('mode', 'unknown').upper()}")
    print(f"Viable for Production: {'YES' if summary.get('encryption_viable') else 'NO'}")
    print(f"Max Error: {summary.get('max_error', 0):.6f}")
    print(f"Avg Expansion Ratio: {summary.get('avg_expansion_ratio', 0):.1f}x")
    print(f"Avg Encryption Time: {summary.get('avg_encryption_time_ms', 0):.1f}ms")
    
    print("\nRecommendations:")
    for rec in report.get("recommendations", [])[:5]:
        print(f"  • {rec}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HE Performance Evaluator")
    parser.add_argument("--output", default="he_evaluation_report.json", help="Output file")
    parser.add_argument("--server", default="http://127.0.0.1:9000", help="HE server URL")
    
    args = parser.parse_args()
    
    HE_SERVER_URL = args.server
    
    run_full_evaluation(args.output)

