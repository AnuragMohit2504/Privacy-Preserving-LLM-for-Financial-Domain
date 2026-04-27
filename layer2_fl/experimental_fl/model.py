import torch
import torch.nn as nn

class SimpleModel(nn.Module):
    def __init__(self, input_dim=10):
        super().__init__()
        self.fc = nn.Linear(input_dim, 2)

    def forward(self, x):
        return self.fc(x)