#C:\Users\anura\Desktop\FINGPT_MAJOR_PROJECT\layer2_fl\client.py

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import flwr as fl
import torch
import numpy as np
import requests
import base64
import uuid
import pandas as pd

from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset
import torch.optim as optim

from fl_config import *
from models.expense_model import ExpenseModel
from dp.dp_engine import make_private
from he.he_utils import create_context, encrypt_weights, decrypt_weights
from db.postgres import log_training_round   # ✅ Postgres logging

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
HE_SERVER = "http://127.0.0.1:9000"




def load_payslip_data(csv_path="C:\\Users\\anura\\Desktop\\FINGPT_MAJOR_PROJECT\\payslips.csv"):

    df = pd.read_csv(csv_path)

    features = [
        "Days_Worked",
        "Basic_Pay",
        "HRA",
        "Special_Allowance",
        "Transport_Allowance",
        "Medical_Allowance",
        "Bonus",
        "PF",
        "Professional_Tax",
        "TDS",
        "Insurance",
        "Loan_Deduction",
        "Net_Pay"
    ]

    X = df[features].values.astype("float32")

    scaler = StandardScaler()
    X = scaler.fit_transform(X)

    X = torch.tensor(X, dtype=torch.float32)

    dataset = TensorDataset(X, X)  # autoencoder style

    return DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=True
    )
    
def load_dummy_data():
    """
    Dummy numeric financial features.
    Replace later with real extracted features.
    """
    X = torch.randn(64, 10)
    y = torch.randint(0, 2, (64,))
    return DataLoader(
        TensorDataset(X, y),
        batch_size=BATCH_SIZE,
        shuffle=True,
    )


class FLClient(fl.client.NumPyClient):
    def __init__(self):
        # 🔹 Client identity (for audit logs)
        self.client_id = str(uuid.uuid4())[:8]
        self.current_round = 0

        # 🔹 Model
        self.model = ExpenseModel(input_dim=13).to(DEVICE)

        # 🔹 Data
        self.loader = load_payslip_data()

        # 🔹 Optimizer / Loss
        self.optimizer = optim.Adam(self.model.parameters(), lr=LR)
        self.criterion = torch.nn.MSELoss()

        # 🔹 HE Context (client-only secret key)
        self.context = create_context()
        self.shapes = [v.shape for v in self.model.state_dict().values()]

        # 🔹 Send PUBLIC HE context to HE server (base64 encoded)
        try:
            requests.post(
                f"{HE_SERVER}/init_context",
                json={
                    "context": base64.b64encode(
                        self.context.serialize()
                    ).decode("utf-8")
                },
            )
        except Exception as e:
            print(f"[HE SERVER] Context init failed: {e}")

        # 🔹 Differential Privacy (before encryption)
        self.privacy_engine = None
        if DP_ENABLED:
            self.model, self.optimizer, self.loader, self.privacy_engine = make_private(
                self.model,
                self.optimizer,
                self.loader,
                NOISE_MULTIPLIER,
                MAX_GRAD_NORM,
            )

    # ==========================
    # Federated Learning Hooks
    # ==========================

    def get_parameters(self, config):
        """
        Encrypt model weights and send to HE server.
        Flower receives dummy placeholders.
        """
        weights = [
            v.detach().cpu().numpy()
            for v in self.model.state_dict().values()
        ]

        encrypted = encrypt_weights(self.context, weights)

        # 🔐 Send encrypted weights to HE server
        try:
            requests.post(
                f"{HE_SERVER}/submit_update",
                json={"weights": encrypted},
            )
        except Exception as e:
            print(f"[HE SERVER] Weight submission failed: {e}")

        # 🧠 Flower parameters are ignored (HE server handles aggregation)
        return [np.zeros(1, dtype=np.float32)]

    def set_parameters(self, parameters):
        """
        Fetch aggregated encrypted model,
        decrypt locally, and load into model.
        """
        try:
            response = requests.get(f"{HE_SERVER}/aggregate").json()
        except Exception as e:
            print(f"[HE SERVER] Aggregation fetch failed: {e}")
            return

        if "weights" not in response:
            return

        decrypted = decrypt_weights(
            self.context,
            response["weights"],
            self.shapes,
        )

        state_dict = dict(
            zip(
                self.model.state_dict().keys(),
                [torch.tensor(w) for w in decrypted],
            )
        )

        self.model.load_state_dict(state_dict, strict=True)

    def fit(self, parameters, config):
        """
        Local training with Differential Privacy.
        """
        self.model.train()

        for _ in range(LOCAL_EPOCHS):
            for x, y in self.loader:
                x, y = x.to(DEVICE), y.to(DEVICE)
                self.optimizer.zero_grad()
                reconstructed = self.model(x)
                loss = self.criterion(reconstructed, x)
                loss.backward()
                self.optimizer.step()

        # 🔍 Privacy budget + Postgres audit logging
        self.current_round += 1
        if self.privacy_engine is not None:
            epsilon = self.privacy_engine.get_epsilon(delta=1e-5)
            print(f"[DP] ε (privacy budget) = {epsilon:.2f}")

            print("Logging training round to Postgres")
            
            # ✅ Store ONLY metadata (no data, no weights)
            log_training_round(
                client_id=self.client_id,
                round_no=self.current_round,
                epsilon=epsilon,
            )
        
        return self.get_parameters(config), len(self.loader.dataset), {}

    def evaluate(self, parameters, config):
        return 0.0, len(self.loader.dataset), {}


# ==========================
# Client Startup
# ==========================

if __name__ == "__main__":
    fl.client.start_numpy_client(
        server_address="127.0.0.1:8081",
        client=FLClient(),
    )