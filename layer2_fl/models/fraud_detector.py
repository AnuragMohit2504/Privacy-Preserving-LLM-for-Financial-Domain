"""
Production-ready Fraud / Anomaly / Credit Risk Detection Module
Supports both unsupervised and supervised evaluation metrics.
"""

import os
import json
import logging
import pickle
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score,
    confusion_matrix, classification_report,
    precision_recall_curve, roc_curve
)

# Import existing autoencoder
from .expense_model import ExpenseModel

logger = logging.getLogger(__name__)


@dataclass
class FraudMetrics:
    """Comprehensive fraud detection metrics container."""
    # Supervised metrics (if labels available)
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    roc_auc: Optional[float] = None
    pr_auc: Optional[float] = None
    accuracy: Optional[float] = None
    
    # Confusion matrix components
    true_positives: Optional[int] = None
    false_positives: Optional[int] = None
    true_negatives: Optional[int] = None
    false_negatives: Optional[int] = None
    
    # Financial-specific metrics
    false_positive_rate: Optional[float] = None
    detection_rate_at_1fpr: Optional[float] = None  # Detection rate at 1% FPR
    detection_rate_at_5fpr: Optional[float] = None  # Detection rate at 5% FPR
    
    # Unsupervised metrics
    outlier_ratio: Optional[float] = None
    mean_reconstruction_error: Optional[float] = None
    std_reconstruction_error: Optional[float] = None
    anomaly_score_threshold: Optional[float] = None
    
    # Model info
    model_type: str = ""
    n_samples: int = 0
    n_features: int = 0
    n_anomalies_detected: int = 0
    timestamp: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


class FraudDetector:
    """
    Ensemble fraud detector combining Isolation Forest and Autoencoder.
    
    Architecture:
    1. Isolation Forest → Unsupervised outlier detection
    2. Autoencoder → Reconstruction error based anomaly detection
    3. Ensemble → Weighted combination of both scores
    
    Supports both unsupervised (no labels) and supervised (with labels) evaluation.
    """
    
    def __init__(
        self,
        input_dim: int = 13,
        if_contamination: float = 0.05,
        if_n_estimators: int = 100,
        autoencoder_hidden_dim: int = 64,
        ensemble_weight_if: float = 0.4,
        ensemble_weight_ae: float = 0.6,
        random_state: int = 42,
        device: str = "cpu"
    ):
        self.input_dim = input_dim
        self.if_contamination = if_contamination
        self.ensemble_weight_if = ensemble_weight_if
        self.ensemble_weight_ae = ensemble_weight_ae
        self.random_state = random_state
        self.device = device
        
        # Isolation Forest
        self.isolation_forest = IsolationForest(
            n_estimators=if_n_estimators,
            contamination=if_contamination,
            random_state=random_state,
            n_jobs=-1
        )
        
        # Autoencoder
        self.autoencoder = ExpenseModel(input_dim=input_dim)
        self.autoencoder.to(device)
        self.autoencoder.eval()
        
        # Scaler
        self.scaler = StandardScaler()
        
        # Thresholds
        self.if_threshold = None
        self.ae_threshold = None
        self.ensemble_threshold = None
        
        # Training artifacts
        self.is_fitted = False
        self.metrics_history: List[FraudMetrics] = []
        
        logger.info(f"FraudDetector initialized: input_dim={input_dim}, "
                   f"IF_contamination={if_contamination}")
    
    def fit(self, X: np.ndarray, y: Optional[np.ndarray] = None, ae_epochs: int = 50) -> 'FraudDetector':
        """
        Fit the fraud detector on training data.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Optional labels (1=fraud/anomaly, 0=normal)
        """
        if len(X) == 0:
            raise ValueError("Empty training data")
        
        self.input_dim = X.shape[1]
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        X_tensor = torch.tensor(X_scaled, dtype=torch.float32).to(self.device)
        
        # Fit Isolation Forest
        logger.info("Training Isolation Forest...")
        self.isolation_forest.fit(X_scaled)
        if_scores = -self.isolation_forest.decision_function(X_scaled)  # Higher = more anomalous
        
        # Fit Autoencoder (unsupervised training)
        logger.info(f"Training Autoencoder for {ae_epochs} epochs...")
        self._train_autoencoder(X_tensor, epochs=ae_epochs, lr=0.001)
        
        # Get reconstruction errors
        with torch.no_grad():
            reconstructed = self.autoencoder(X_tensor)
            ae_errors = torch.mean((X_tensor - reconstructed) ** 2, dim=1).cpu().numpy()
        
        # Normalize scores to [0, 1]
        if_scores_norm = self._normalize_scores(if_scores)
        ae_errors_norm = self._normalize_scores(ae_errors)
        
        # Compute ensemble scores
        ensemble_scores = (
            self.ensemble_weight_if * if_scores_norm +
            self.ensemble_weight_ae * ae_errors_norm
        )
        
        # Set thresholds
        if y is not None:
            # Supervised threshold optimization
            self.ensemble_threshold = self._optimize_threshold(ensemble_scores, y)
            self.if_threshold = self._optimize_threshold(if_scores_norm, y)
            self.ae_threshold = self._optimize_threshold(ae_errors_norm, y)
        else:
            # Unsupervised threshold (percentile-based)
            self.ensemble_threshold = np.percentile(ensemble_scores, 95)
            self.if_threshold = np.percentile(if_scores_norm, 95)
            self.ae_threshold = np.percentile(ae_errors_norm, 95)
        
        self.is_fitted = True
        logger.info(f"FraudDetector fitted. Thresholds: ensemble={self.ensemble_threshold:.4f}, "
                   f"IF={self.if_threshold:.4f}, AE={self.ae_threshold:.4f}")
        
        return self
    
    def _train_autoencoder(
        self,
        X: torch.Tensor,
        epochs: int = 50,
        lr: float = 0.001,
        batch_size: int = 32
    ):
        """Train the autoencoder on normal data only."""
        self.autoencoder.train()
        optimizer = torch.optim.Adam(self.autoencoder.parameters(), lr=lr)
        criterion = nn.MSELoss()
        
        dataset = torch.utils.data.TensorDataset(X, X)
        loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)
        
        for epoch in range(epochs):
            total_loss = 0
            for batch_x, _ in loader:
                optimizer.zero_grad()
                reconstructed = self.autoencoder(batch_x)
                loss = criterion(reconstructed, batch_x)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            
            if (epoch + 1) % 10 == 0:
                logger.info(f"  AE Epoch {epoch+1}/{epochs}, Loss: {total_loss/len(loader):.6f}")
        
        self.autoencoder.eval()
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict anomaly labels (1=anomaly, 0=normal)."""
        scores = self.decision_function(X)
        return (scores >= self.ensemble_threshold).astype(int)
    
    def decision_function(self, X: np.ndarray) -> np.ndarray:
        """Return anomaly scores (higher = more anomalous)."""
        if not self.is_fitted:
            raise RuntimeError("FraudDetector must be fitted before prediction")
        
        X_scaled = self.scaler.transform(X)
        X_tensor = torch.tensor(X_scaled, dtype=torch.float32).to(self.device)
        
        # Isolation Forest scores
        if_scores = -self.isolation_forest.decision_function(X_scaled)
        if_scores_norm = self._normalize_scores(if_scores)
        
        # Autoencoder scores
        with torch.no_grad():
            reconstructed = self.autoencoder(X_tensor)
            ae_errors = torch.mean((X_tensor - reconstructed) ** 2, dim=1).cpu().numpy()
        ae_errors_norm = self._normalize_scores(ae_errors)
        
        # Ensemble
        ensemble_scores = (
            self.ensemble_weight_if * if_scores_norm +
            self.ensemble_weight_ae * ae_errors_norm
        )
        
        return ensemble_scores
    
    def evaluate(
        self,
        X: np.ndarray,
        y: Optional[np.ndarray] = None,
        dataset_name: str = "test"
    ) -> FraudMetrics:
        """
        Comprehensive evaluation with all relevant metrics.
        
        Args:
            X: Feature matrix
            y: True labels (optional, for supervised metrics)
            dataset_name: Name for logging
        
        Returns:
            FraudMetrics object with all computed metrics
        """
        if not self.is_fitted:
            raise RuntimeError("FraudDetector must be fitted before evaluation")
        
        scores = self.decision_function(X)
        predictions = (scores >= self.ensemble_threshold).astype(int)
        
        n_anomalies = int(predictions.sum())
        outlier_ratio = n_anomalies / len(X) if len(X) > 0 else 0.0
        
        metrics = FraudMetrics(
            model_type="IsolationForest+Autoencoder_Ensemble",
            n_samples=len(X),
            n_features=X.shape[1],
            n_anomalies_detected=n_anomalies,
            outlier_ratio=outlier_ratio,
            anomaly_score_threshold=self.ensemble_threshold,
            timestamp=datetime.utcnow().isoformat()
        )
        
        # Unsupervised metrics (always available)
        X_scaled = self.scaler.transform(X)
        X_tensor = torch.tensor(X_scaled, dtype=torch.float32).to(self.device)
        with torch.no_grad():
            reconstructed = self.autoencoder(X_tensor)
            ae_errors = torch.mean((X_tensor - reconstructed) ** 2, dim=1).cpu().numpy()
        
        metrics.mean_reconstruction_error = float(np.mean(ae_errors))
        metrics.std_reconstruction_error = float(np.std(ae_errors))
        
        # Supervised metrics (if labels available)
        if y is not None:
            # Basic classification metrics
            metrics.precision = float(precision_score(y, predictions, zero_division=0))
            metrics.recall = float(recall_score(y, predictions, zero_division=0))
            metrics.f1_score = float(f1_score(y, predictions, zero_division=0))
            metrics.accuracy = float(np.mean(predictions == y))
            
            # ROC-AUC and PR-AUC
            try:
                metrics.roc_auc = float(roc_auc_score(y, scores))
                metrics.pr_auc = float(average_precision_score(y, scores))
            except ValueError:
                logger.warning("Could not compute ROC-AUC (possibly only one class present)")
            
            # Confusion matrix
            tn, fp, fn, tp = confusion_matrix(y, predictions, labels=[0, 1]).ravel()
            metrics.true_positives = int(tp)
            metrics.false_positives = int(fp)
            metrics.true_negatives = int(tn)
            metrics.false_negatives = int(fn)
            
            # Financial-specific metrics
            metrics.false_positive_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0
            
            # Detection rate at specific FPR thresholds
            fpr, tpr, _ = roc_curve(y, scores)
            metrics.detection_rate_at_1fpr = self._detection_rate_at_fpr(fpr, tpr, 0.01)
            metrics.detection_rate_at_5fpr = self._detection_rate_at_fpr(fpr, tpr, 0.05)
        
        self.metrics_history.append(metrics)
        
        logger.info(f"Evaluation on {dataset_name}:")
        logger.info(f"  Samples: {metrics.n_samples}, Anomalies detected: {metrics.n_anomalies_detected}")
        if metrics.f1_score is not None:
            logger.info(f"  Precision: {metrics.precision:.4f}, Recall: {metrics.recall:.4f}, F1: {metrics.f1_score:.4f}")
        if metrics.roc_auc is not None:
            logger.info(f"  ROC-AUC: {metrics.roc_auc:.4f}, PR-AUC: {metrics.pr_auc:.4f}")
        
        return metrics
    
    def _normalize_scores(self, scores: np.ndarray) -> np.ndarray:
        """Min-max normalize scores to [0, 1]."""
        min_val = np.min(scores)
        max_val = np.max(scores)
        if max_val - min_val < 1e-10:
            return np.zeros_like(scores)
        return (scores - min_val) / (max_val - min_val)
    
    def _optimize_threshold(self, scores: np.ndarray, y: np.ndarray) -> float:
        """Find optimal threshold maximizing F1 score."""
        best_threshold = 0.5
        best_f1 = 0.0
        
        for threshold in np.linspace(0, 1, 100):
            preds = (scores >= threshold).astype(int)
            f1 = f1_score(y, preds, zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_threshold = threshold
        
        return best_threshold
    
    def _detection_rate_at_fpr(
        self,
        fpr: np.ndarray,
        tpr: np.ndarray,
        target_fpr: float
    ) -> float:
        """Get detection rate (TPR) at a specific FPR."""
        idx = np.where(fpr <= target_fpr)[0]
        if len(idx) > 0:
            return float(np.max(tpr[idx]))
        return 0.0
    
    def save(self, path: str):
        """Save model to disk."""
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        state = {
            'isolation_forest': self.isolation_forest,
            'autoencoder_state': self.autoencoder.state_dict(),
            'scaler': self.scaler,
            'thresholds': {
                'ensemble': self.ensemble_threshold,
                'if': self.if_threshold,
                'ae': self.ae_threshold
            },
            'config': {
                'input_dim': self.input_dim,
                'if_contamination': self.if_contamination,
                'ensemble_weight_if': self.ensemble_weight_if,
                'ensemble_weight_ae': self.ensemble_weight_ae
            },
            'metrics_history': [m.to_dict() for m in self.metrics_history]
        }
        with open(path, 'wb') as f:
            pickle.dump(state, f)
        logger.info(f"FraudDetector saved to {path}")
    
    @classmethod
    def load(cls, path: str, device: str = "cpu") -> 'FraudDetector':
        """Load model from disk."""
        with open(path, 'rb') as f:
            state = pickle.load(f)
        
        config = state['config']
        detector = cls(
            input_dim=config['input_dim'],
            if_contamination=config['if_contamination'],
            ensemble_weight_if=config['ensemble_weight_if'],
            ensemble_weight_ae=config['ensemble_weight_ae'],
            device=device
        )
        
        detector.isolation_forest = state['isolation_forest']
        detector.autoencoder.load_state_dict(state['autoencoder_state'])
        detector.scaler = state['scaler']
        detector.ensemble_threshold = state['thresholds']['ensemble']
        detector.if_threshold = state['thresholds']['if']
        detector.ae_threshold = state['thresholds']['ae']
        detector.is_fitted = True
        
        logger.info(f"FraudDetector loaded from {path}")
        return detector


def generate_synthetic_fraud_labels(
    df: pd.DataFrame,
    fraud_rate: float = 0.05,
    random_state: int = 42
) -> np.ndarray:
    """
    Generate synthetic fraud labels for testing.
    
    Strategy:
    - High net pay with low days worked → potential fraud
    - Unusual deduction ratios → potential fraud
    - Extreme bonus values → potential fraud
    """
    np.random.seed(random_state)
    n = len(df)
    labels = np.zeros(n, dtype=int)
    
    # Rule 1: High net pay but low days worked (ghost employee)
    if 'Days_Worked' in df.columns and 'Net_Pay' in df.columns:
        days_norm = (df['Days_Worked'] - df['Days_Worked'].mean()) / df['Days_Worked'].std()
        pay_norm = (df['Net_Pay'] - df['Net_Pay'].mean()) / df['Net_Pay'].std()
        ghost_score = pay_norm - days_norm
        ghost_indices = df[ghost_score > ghost_score.quantile(0.95)].index
        labels[ghost_indices] = 1
    
    # Rule 2: Unusually high deductions
    if 'Total_Deductions' in df.columns and 'Gross_Earnings' in df.columns:
        ded_ratio = df['Total_Deductions'] / df['Gross_Earnings'].clip(lower=1)
        high_ded = df[ded_ratio > ded_ratio.quantile(0.97)].index
        labels[high_ded] = 1
    
    # Rule 3: Extreme bonus
    if 'Bonus' in df.columns:
        bonus_norm = (df['Bonus'] - df['Bonus'].mean()) / df['Bonus'].std()
        extreme_bonus = df[bonus_norm > 3].index
        labels[extreme_bonus] = 1
    
    # Ensure we have at least some fraud cases
    n_fraud = int(n * fraud_rate)
    current_fraud = labels.sum()
    if current_fraud < n_fraud:
        additional = np.random.choice(
            np.where(labels == 0)[0],
            size=n_fraud - current_fraud,
            replace=False
        )
        labels[additional] = 1
    
    return labels


if __name__ == "__main__":
    # Quick test
    print("Testing FraudDetector...")
    
    # Create synthetic data
    np.random.seed(42)
    X_normal = np.random.randn(900, 10)
    X_fraud = np.random.randn(100, 10) * 3 + 5  # Shifted distribution
    X = np.vstack([X_normal, X_fraud])
    y = np.array([0] * 900 + [1] * 100)
    
    # Fit and evaluate
    detector = FraudDetector(input_dim=10)
    detector.fit(X, y)
    metrics = detector.evaluate(X, y, "synthetic_test")
    
    print("\n" + "="*50)
    print("FRAUD DETECTION METRICS")
    print("="*50)
    print(metrics.to_json())

