# Advanced outcome model comparison

## Time-aware comparison

{
  "champion": {
    "log_loss": 0.8553559629684756,
    "brier_score": 0.5043166982637002,
    "accuracy": 0.6119610570236439
  },
  "logistic_baseline": {
    "log_loss": 0.8618966046721029,
    "brier_score": 0.5079161961906685,
    "accuracy": 0.6084840055632823
  },
  "xgboost_blend_weight": 0.4,
  "validation_log_loss": 0.8466021570129533
}

## Selection

The blend weight is selected only on chronological validation data. A zero weight means the nonlinear model did not add honest held-out value.
