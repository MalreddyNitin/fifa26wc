import numpy as np
from sklearn.metrics import accuracy_score, log_loss


def multiclass_brier(y_true, probabilities, labels):
    positions = {label: index for index, label in enumerate(labels)}
    encoded = np.zeros_like(probabilities, dtype=float)
    for row, label in enumerate(y_true):
        encoded[row, positions[label]] = 1
    return np.mean(np.sum((probabilities - encoded) ** 2, axis=1))


def classification_metrics(y_true, probabilities, labels):
    probabilities = np.asarray(probabilities, dtype=float)
    probabilities = np.clip(probabilities, 1e-12, 1)
    probabilities = probabilities / probabilities.sum(axis=1, keepdims=True)
    positions = {label: index for index, label in enumerate(labels)}
    encoded_y = np.asarray([positions[label] for label in y_true])
    predicted = np.asarray(labels)[np.argmax(probabilities, axis=1)]
    return {
        "log_loss": log_loss(
            encoded_y,
            probabilities,
            labels=list(range(len(labels))),
        ),
        "brier_score": multiclass_brier(y_true, probabilities, labels),
        "accuracy": accuracy_score(y_true, predicted),
    }


def chronological_split(frame, train_fraction=0.7, validation_fraction=0.15):
    ordered = frame.sort_values(["kickoff_utc", "event_id"], kind="stable")
    n = len(ordered)
    train_end = max(1, int(n * train_fraction))
    validation_end = max(train_end + 1, int(n * (train_fraction + validation_fraction)))
    return (
        ordered.iloc[:train_end].copy(),
        ordered.iloc[train_end:validation_end].copy(),
        ordered.iloc[validation_end:].copy(),
    )
