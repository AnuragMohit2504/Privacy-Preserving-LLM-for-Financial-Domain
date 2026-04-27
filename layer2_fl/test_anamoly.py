import torch
import pandas as pd
from models.expense_model import ExpenseModel

model = ExpenseModel(input_dim=13)
model.eval()

df = pd.read_csv("payslips.csv")

features = [
"Days_Worked","Basic_Pay","HRA","Special_Allowance",
"Transport_Allowance","Medical_Allowance","Bonus",
"PF","Professional_Tax","TDS","Insurance",
"Loan_Deduction","Net_Pay"
]

X = torch.tensor(df[features].values, dtype=torch.float32)

with torch.no_grad():
    reconstructed = model(X)

error = torch.mean((X - reconstructed) ** 2, dim=1)

df["anomaly_score"] = error.numpy()
df["anomaly"] = df["anomaly_score"] > 0.02

print(df[["Employee_ID","anomaly_score","anomaly"]])