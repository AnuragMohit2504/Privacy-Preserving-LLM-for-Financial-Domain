#expense_classifier.py

import torch
import torch.nn as nn

class ExpenseModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(10, 32),
            nn.ReLU(),
            nn.Linear(32, 2)
        )

    def forward(self, x):
        return self.net(x)
#expense_model.py
import torch
import torch.nn as nn

class ExpenseModel(nn.Module):
    """
    Simple federatable model.
    This is NOT the LLM.
    This learns numeric spending patterns only.
    """

    def __init__(self, input_dim: int = 10, num_classes: int = 2):
        super().__init__()

        self.model = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.Linear(32, num_classes)
        )

    def forward(self, x):
        return self.model(x)
ROUNDS = 5
LOCAL_EPOCHS = 3
BATCH_SIZE = 16
LR = 0.001

DP_ENABLED = True
NOISE_MULTIPLIER = 1.0
MAX_GRAD_NORM = 1.0

INPUT_DIM = 10
NUM_CLASSES = 2