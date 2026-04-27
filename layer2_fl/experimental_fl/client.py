from model import SimpleModel
from train import train_local
import numpy as np

def simulate_client(features):
    model = SimpleModel(input_dim=len(features[0]))

    # fake labels for now
    labels = np.random.randint(0, 2, len(features))

    weights = train_local(model, features, labels)

    return weights