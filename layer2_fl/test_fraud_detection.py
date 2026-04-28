"""
Fraud Detection Benchmark & Performance Testing
Tests the FraudDetector on real payslip data with comprehensive metrics.
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from typing import Dict, List

import numpy as np
import pandas as pd
import torch
from sklearn.model_selection import train_test_split

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.fraud_detector import FraudDetector, generate_synthetic_fraud_labels, FraudMetrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def load_payslip_data(csv_path: str) -> pd.DataFrame:
    """Load payslip CSV data."""
    if not os.path.exists(csv_path):
        # Try relative paths
        alt_paths = [
            os.path.join(os.path.dirname(__file__), "..", "payslips.csv"),
            os.path.join(os.path.dirname(__file__), "..", "..", "payslips.csv"),
            "payslips.csv"
        ]
        for alt in alt_paths:
            if os.path.exists(alt):
                csv_path = alt
                break
        else:
            raise FileNotFoundError(f"Payslip CSV not found. Tried: {csv_path}")
    
    df = pd.read_csv(csv_path)
    logger.info(f"Loaded {len(df)} payslip records from {csv_path}")
    return df


def prepare_features(df: pd.DataFrame) -> np.ndarray:
    """Extract numeric features from payslip dataframe."""
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    # Exclude ID columns
    exclude = ['Employee_ID', 'id', 'ID']
    feature_cols = [c for c in numeric_cols if c not in exclude]
    
    if not feature_cols:
        raise ValueError("No numeric feature columns found")
    
    X = df[feature_cols].fillna(0).values.astype(np.float32)
    logger.info(f"Feature matrix shape: {X.shape}, columns: {feature_cols}")
    return X, feature_cols


def run_benchmark(
    csv_path: str,
    test_size: float = 0.2,
    fraud_rate: float = 0.05,
    output_dir: str = "./analysis_results"
) -> Dict:
    """
    Run complete fraud detection benchmark.
    
    Returns:
        Dictionary with all metrics and file paths
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info("="*60)
    logger.info("FRAUD DETECTION BENCHMARK")
    logger.info("="*60)
    
    # Load data
    df = load_payslip_data(csv_path)
    X, feature_cols = prepare_features(df)
    
    # Generate synthetic fraud labels for evaluation
    y = generate_synthetic_fraud_labels(df, fraud_rate=fraud_rate)
    logger.info(f"Fraud distribution: {np.bincount(y)} (fraud rate: {y.mean():.2%})")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=y
    )
    
    # Initialize detector
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")
    
    detector = FraudDetector(
        input_dim=X.shape[1],
        if_contamination=max(0.01, fraud_rate * 1.5),  # Slightly higher for IF
        ensemble_weight_if=0.4,
        ensemble_weight_ae=0.6,
        device=device
    )
    
    # Fit
    logger.info("\n[1/4] Training fraud detector...")
    detector.fit(X_train, y_train)
    
    # Evaluate on train set
    logger.info("\n[2/4] Evaluating on training set...")
    train_metrics = detector.evaluate(X_train, y_train, "train")
    
    # Evaluate on test set
    logger.info("\n[3/4] Evaluating on test set...")
    test_metrics = detector.evaluate(X_test, y_test, "test")
    
    # Cross-validation style: evaluate on full dataset
    logger.info("\n[4/4] Evaluating on full dataset...")
    full_metrics = detector.evaluate(X, y, "full")
    
    # Save model
    model_path = os.path.join(output_dir, f"fraud_detector_{timestamp}.pkl")
    detector.save(model_path)
    
    # Save metrics
    results = {
        "timestamp": timestamp,
        "dataset": {
            "path": csv_path,
            "n_samples": len(df),
            "n_features": len(feature_cols),
            "feature_columns": feature_cols,
            "fraud_rate": float(y.mean()),
            "train_samples": len(X_train),
            "test_samples": len(X_test)
        },
        "train_metrics": train_metrics.to_dict(),
        "test_metrics": test_metrics.to_dict(),
        "full_metrics": full_metrics.to_dict(),
        "model_path": model_path
    }
    
    metrics_path = os.path.join(output_dir, f"fraud_metrics_{timestamp}.json")
    with open(metrics_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    # Generate report
    report_path = os.path.join(output_dir, f"fraud_report_{timestamp}.txt")
    generate_text_report(results, report_path)
    
    # Print summary
    print_summary(results)
    
    logger.info(f"\nResults saved to:")
    logger.info(f"  Model: {model_path}")
    logger.info(f"  Metrics JSON: {metrics_path}")
    logger.info(f"  Report: {report_path}")
    
    return results


def generate_text_report(results: Dict, path: str):
    """Generate human-readable text report."""
    with open(path, 'w') as f:
        f.write("="*70 + "\n")
        f.write("FRAUD DETECTION BENCHMARK REPORT\n")
        f.write("="*70 + "\n\n")
        
        f.write(f"Timestamp: {results['timestamp']}\n")
        f.write(f"Dataset: {results['dataset']['path']}\n")
        f.write(f"Samples: {results['dataset']['n_samples']}\n")
        f.write(f"Features: {results['dataset']['n_features']}\n")
        f.write(f"Feature Columns: {', '.join(results['dataset']['feature_columns'])}\n")
        f.write(f"Fraud Rate: {results['dataset']['fraud_rate']:.2%}\n\n")
        
        for split in ['train_metrics', 'test_metrics', 'full_metrics']:
            m = results[split]
            f.write("-"*70 + "\n")
            f.write(f"{split.replace('_', ' ').upper()}\n")
            f.write("-"*70 + "\n")
            
            f.write(f"  Model Type: {m['model_type']}\n")
            f.write(f"  Samples: {m['n_samples']}\n")
            f.write(f"  Anomalies Detected: {m['n_anomalies_detected']}\n")
            f.write(f"  Outlier Ratio: {m['outlier_ratio']:.2%}\n\n")
            
            if m['precision'] is not None:
                f.write("  SUPERVISED METRICS:\n")
                f.write(f"    Accuracy:  {m['accuracy']:.4f}\n")
                f.write(f"    Precision: {m['precision']:.4f}\n")
                f.write(f"    Recall:    {m['recall']:.4f}\n")
                f.write(f"    F1-Score:  {m['f1_score']:.4f}\n")
                f.write(f"    ROC-AUC:   {m['roc_auc']:.4f}\n")
                f.write(f"    PR-AUC:    {m['pr_auc']:.4f}\n\n")
                
                f.write("  CONFUSION MATRIX:\n")
                f.write(f"    True Positives:  {m['true_positives']}\n")
                f.write(f"    False Positives: {m['false_positives']}\n")
                f.write(f"    True Negatives:  {m['true_negatives']}\n")
                f.write(f"    False Negatives: {m['false_negatives']}\n\n")
                
                f.write("  FINANCIAL-SPECIFIC METRICS:\n")
                f.write(f"    False Positive Rate: {m['false_positive_rate']:.4f}\n")
                f.write(f"    Detection Rate @ 1% FPR: {m['detection_rate_at_1fpr']:.4f}\n")
                f.write(f"    Detection Rate @ 5% FPR: {m['detection_rate_at_5fpr']:.4f}\n\n")
            
            f.write("  UNSUPERVISED METRICS:\n")
            f.write(f"    Mean Reconstruction Error: {m['mean_reconstruction_error']:.6f}\n")
            f.write(f"    Std Reconstruction Error:  {m['std_reconstruction_error']:.6f}\n")
            f.write(f"    Anomaly Threshold: {m['anomaly_score_threshold']:.6f}\n\n")


def print_summary(results: Dict):
    """Print concise summary to console."""
    print("\n" + "="*70)
    print("FRAUD DETECTION BENCHMARK SUMMARY")
    print("="*70)
    
    test = results['test_metrics']
    print(f"\nDataset: {results['dataset']['n_samples']} samples, "
          f"{results['dataset']['fraud_rate']:.1%} fraud rate")
    
    if test['precision'] is not None:
        print(f"\nTest Set Performance:")
        print(f"  Accuracy:  {test['accuracy']:.4f}")
        print(f"  Precision: {test['precision']:.4f}")
        print(f"  Recall:    {test['recall']:.4f}")
        print(f"  F1-Score:  {test['f1_score']:.4f}")
        print(f"  ROC-AUC:   {test['roc_auc']:.4f}")
        print(f"  PR-AUC:    {test['pr_auc']:.4f}")
        print(f"\nFinancial Metrics:")
        print(f"  FPR:       {test['false_positive_rate']:.4f}")
        print(f"  DR@1%FPR:  {test['detection_rate_at_1fpr']:.4f}")
        print(f"  DR@5%FPR:  {test['detection_rate_at_5fpr']:.4f}")
    
    print(f"\nUnsupervised Metrics:")
    print(f"  Outlier Ratio: {test['outlier_ratio']:.2%}")
    print(f"  Mean Recon Error: {test['mean_reconstruction_error']:.6f}")
    print("="*70)


def compare_configurations(csv_path: str, output_dir: str = "./analysis_results"):
    """Run benchmark with multiple configurations and compare."""
    configs = [
        {"name": "Balanced", "if_weight": 0.5, "ae_weight": 0.5},
        {"name": "IF_Heavy", "if_weight": 0.7, "ae_weight": 0.3},
        {"name": "AE_Heavy", "if_weight": 0.3, "ae_weight": 0.7},
    ]
    
    results = []
    for config in configs:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing configuration: {config['name']}")
        logger.info(f"{'='*60}")
        
        df = load_payslip_data(csv_path)
        X, feature_cols = prepare_features(df)
        y = generate_synthetic_fraud_labels(df)
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        detector = FraudDetector(
            input_dim=X.shape[1],
            ensemble_weight_if=config['if_weight'],
            ensemble_weight_ae=config['ae_weight']
        )
        detector.fit(X_train, y_train)
        metrics = detector.evaluate(X_test, y_test, config['name'])
        
        results.append({
            'config': config['name'],
            'f1': metrics.f1_score,
            'roc_auc': metrics.roc_auc,
            'fpr': metrics.false_positive_rate,
            'dr_1fpr': metrics.detection_rate_at_1fpr
        })
    
    # Print comparison
    print("\n" + "="*70)
    print("CONFIGURATION COMPARISON")
    print("="*70)
    print(f"{'Config':<12} {'F1':>8} {'ROC-AUC':>8} {'FPR':>8} {'DR@1%FPR':>10}")
    print("-"*70)
    for r in results:
        print(f"{r['config']:<12} {r['f1']:>8.4f} {r['roc_auc']:>8.4f} "
              f"{r['fpr']:>8.4f} {r['dr_1fpr']:>10.4f}")
    
    # Save comparison
    comparison_path = os.path.join(output_dir, "config_comparison.json")
    os.makedirs(output_dir, exist_ok=True)
    with open(comparison_path, 'w') as f:
        json.dump(results, f, indent=2)
    logger.info(f"Comparison saved to {comparison_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fraud Detection Benchmark")
    parser.add_argument("--csv", default="payslips.csv", help="Path to payslip CSV")
    parser.add_argument("--test-size", type=float, default=0.2, help="Test set ratio")
    parser.add_argument("--fraud-rate", type=float, default=0.05, help="Synthetic fraud rate")
    parser.add_argument("--output", default="./analysis_results", help="Output directory")
    parser.add_argument("--compare", action="store_true", help="Compare configurations")
    
    args = parser.parse_args()
    
    if args.compare:
        compare_configurations(args.csv, args.output)
    else:
        run_benchmark(args.csv, args.test_size, args.fraud_rate, args.output)

