# fl_config.py

from dataclasses import dataclass, field
from typing import List
import torch

# =========================
# Device
# =========================

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# =========================
# Training Config
# =========================

BATCH_SIZE = 16
LR = 0.001
LOCAL_EPOCHS = 2

# =========================
# Differential Privacy
# =========================

DP_ENABLED = True
NOISE_MULTIPLIER = 1.1
MAX_GRAD_NORM = 1.0


# =========================
# Federated Learning Config
# =========================

@dataclass(frozen=True)
class FLConfig:

    # FL rounds
    ROUNDS: int = 5
    MIN_FIT_CLIENTS: int = 2
    MIN_EVAL_CLIENTS: int = 2
    MIN_AVAILABLE_CLIENTS: int = 2

    # Homomorphic Encryption parameters
    HE_POLY_MOD_DEGREE: int = 8192

    HE_COEFF_MOD_BIT_SIZES: List[int] = field(
        default_factory=lambda: [60, 40, 40, 60]
    )

    # metadata
    PROJECT_NAME: str = "FINGPT_FL_LAYER2"
    VERSION: str = "1.0.0"