# Outcome model card

Predicts regulation-time home win, draw, and away win probabilities. The
baseline is multinomial logistic regression using pre-match Elo, ranking,
context, and shifted rolling form. The advanced candidate is a time-validated
XGBoost blend; its blend weight is selected only on chronological validation
data.

Primary metrics are multiclass log loss and Brier score. Accuracy is secondary.
Do not interpret model probabilities as guaranteed outcomes or use current
match statistics as inputs.
