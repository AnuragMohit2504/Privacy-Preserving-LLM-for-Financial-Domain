from model import SimpleModel
import torch

def aggregate(weights_list):
    avg_weights = {}

    for key in weights_list[0].keys():
        avg_weights[key] = sum(w[key] for w in weights_list) / len(weights_list)

    return avg_weights


def update_global_model(global_model, aggregated_weights):
    global_model.load_state_dict(aggregated_weights)
    return global_model