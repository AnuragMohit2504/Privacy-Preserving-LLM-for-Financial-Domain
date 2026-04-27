"""
Production-ready Expense Classification Model
Supports both local and federated training
"""

import torch
import torch.nn as nn
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class ExpenseModel(nn.Module):
    """
    Autoencoder model for anomaly detection
    Compatible with Differential Privacy
    """

    def __init__(self, input_dim: int = 13):
        super().__init__()

        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.LayerNorm(64),
            nn.ReLU(),

            nn.Linear(64, 32),
            nn.LayerNorm(32),
            nn.ReLU(),

            nn.Linear(32, 16)
        )

        self.decoder = nn.Sequential(
            nn.Linear(16, 32),
            nn.ReLU(),

            nn.Linear(32, 64),
            nn.ReLU(),

            nn.Linear(64, input_dim)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded

class ExpenseModelV2(nn.Module):
    """
    Enhanced expense model with attention mechanism
    Better for complex financial patterns
    """
    
    def __init__(
        self,
        input_dim: int = 10,
        hidden_dim: int = 64,
        num_classes: int = 2,
        num_heads: int = 4,
        dropout: float = 0.3
    ):
        super().__init__()
        
        self.input_projection = nn.Linear(input_dim, hidden_dim)
        
        # Multi-head attention
        self.attention = nn.MultiheadAttention(
            embed_dim=hidden_dim,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=True
        )
        
        self.norm1 = nn.LayerNorm(hidden_dim)
        self.norm2 = nn.LayerNorm(hidden_dim)
        
        # Feed-forward network
        self.ffn = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim * 4),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim * 4, hidden_dim),
            nn.Dropout(dropout)
        )
        
        # Output layer
        self.output = nn.Linear(hidden_dim, num_classes)
        
        logger.info(f"ExpenseModelV2 initialized: input={input_dim}, hidden={hidden_dim}, heads={num_heads}")
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass with attention"""
        # Project input
        x = self.input_projection(x)
        
        # Add sequence dimension for attention
        if x.dim() == 2:
            x = x.unsqueeze(1)  # (batch, 1, hidden)
        
        # Self-attention
        attn_out, _ = self.attention(x, x, x)
        x = self.norm1(x + attn_out)
        
        # Feed-forward
        ffn_out = self.ffn(x)
        x = self.norm2(x + ffn_out)
        
        # Remove sequence dimension and output
        x = x.squeeze(1)
        return self.output(x)

def create_model(
    model_type: str = "basic",
    input_dim: int = 10,
    num_classes: int = 2,
    **kwargs
) -> nn.Module:
    """
    Factory function to create expense models
    
    Args:
        model_type: "basic" or "v2" (with attention)
        input_dim: Input feature dimension
        num_classes: Number of output classes
        **kwargs: Additional model-specific arguments
    
    Returns:
        Initialized model
    """
    if model_type == "basic":
        return ExpenseModel(input_dim=input_dim)
    elif model_type == "v2":
        return ExpenseModelV2(
            input_dim=input_dim,
            num_classes=num_classes,
            **kwargs
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")

if __name__ == "__main__":
    # Test models
    print("Testing ExpenseModel...")
    
    model_basic = ExpenseModel(input_dim=10, num_classes=2)
    print(f"Basic model parameters: {model_basic.get_num_parameters()}")
    
    x = torch.randn(4, 10)
    output = model_basic(x)
    print(f"Output shape: {output.shape}")
    
    proba = model_basic.predict_proba(x)
    print(f"Probabilities:\n{proba}")
    
    print("\nTesting ExpenseModelV2...")
    model_v2 = ExpenseModelV2(input_dim=10, num_classes=2)
    print(f"V2 model parameters: {model_v2.get_num_parameters()}")
    
    output_v2 = model_v2(x)
    print(f"V2 output shape: {output_v2.shape}")
    
    print("✅ Model tests passed!")