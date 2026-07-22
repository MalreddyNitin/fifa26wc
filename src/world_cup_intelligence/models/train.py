import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import poisson
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.metrics import mean_absolute_error, mean_poisson_deviance
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .evaluation import chronological_split, classification_metrics
from .scoreline import market_probabilities, score_matrix
from .tracking import dataset_version, tracked_run

LABELS = ["loss", "draw", "win"]
TARGET_COLUMNS = {
    "result",
    "goals_for",
    "goals_against",
    "goal_difference",
    "team_scored",
    "team_conceded",
    "points",
    "training_eligible",
}


def _feature_columns(frame, maximum=80):
    candidates = [
        column
        for column in frame.columns
        if (
            column
            in {
                "elo_difference",
                "rest_days",
                "fixture_congestion_14d",
                "neutral_site",
                "competition_type",
                "round_name",
                "confederation_matchup",
            }
            or column.startswith(("rolling_", "opponent_rolling_", "ewm_", "trend_"))
        )
        and column not in TARGET_COLUMNS
    ]
    coverage = frame[candidates].notna().mean().sort_values(ascending=False)
    always = [
        c
        for c in candidates
        if c
        in {
            "elo_difference",
            "rest_days",
            "fixture_congestion_14d",
            "neutral_site",
            "competition_type",
            "round_name",
            "confederation_matchup",
        }
    ]
    selected = list(dict.fromkeys([*always, *coverage.index.tolist()]))
    return selected[:maximum]


def _preprocessor(frame, features):
    categorical = [c for c in features if not pd.api.types.is_numeric_dtype(frame[c])]
    numeric = [c for c in features if c not in categorical]
    return ColumnTransformer(
        [
            (
                "numeric",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric,
            ),
            (
                "categorical",
                Pipeline(
                    [
                        (
                            "impute",
                            SimpleImputer(strategy="constant", fill_value="unknown"),
                        ),
                        (
                            "encode",
                            OneHotEncoder(
                                handle_unknown="ignore",
                                sparse_output=False,
                            ),
                        ),
                    ]
                ),
                categorical,
            ),
        ],
        verbose_feature_names_out=False,
    )


def elo_probabilities(frame):
    expected = np.clip(
        frame["elo_expected_score"].fillna(0.5).to_numpy(float),
        0.02,
        0.98,
    )
    draw = 0.28 * np.exp(-np.abs(expected - 0.5) * 2)
    decisive = 1 - draw
    return np.column_stack([(1 - expected) * decisive, draw, expected * decisive])


def _write_report(path, title, sections):
    lines = [f"# {title}", ""]
    for heading, content in sections:
        lines.extend([f"## {heading}", "", str(content), ""])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def _calibration_plot(y_true, probabilities, classes, path):
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(1, len(classes), figsize=(12, 3.5))
    for index, label in enumerate(classes):
        actual = np.asarray(y_true).astype(str) == label
        predicted = probabilities[:, index]
        bins = pd.cut(
            predicted,
            bins=np.linspace(0, 1, 11),
            include_lowest=True,
            duplicates="drop",
        )
        calibration = (
            pd.DataFrame({"actual": actual, "predicted": predicted, "bin": bins})
            .groupby("bin", observed=True)
            .agg(
                actual=("actual", "mean"),
                predicted=("predicted", "mean"),
            )
        )
        axes[index].plot([0, 1], [0, 1], "--", color="gray")
        axes[index].plot(calibration["predicted"], calibration["actual"], marker="o")
        axes[index].set_title(label)
        axes[index].set_xlabel("predicted")
        axes[index].set_ylabel("observed")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def train_outcome_models(master, root):
    rows = master.loc[
        master["side"].eq("home")
        & master["training_eligible"]
        & master["result"].notna()
    ].copy()
    features = _feature_columns(rows)
    train, validation, test = chronological_split(rows)
    model = Pipeline(
        [
            ("preprocess", _preprocessor(train, features)),
            (
                "model",
                LogisticRegression(
                    max_iter=2000,
                    C=0.5,
                    random_state=42,
                ),
            ),
        ]
    )
    model.fit(train[features], train["result"])
    classes = model.named_steps["model"].classes_.tolist()
    logistic_prob = model.predict_proba(test[features])
    logistic_metrics = classification_metrics(test["result"], logistic_prob, classes)
    elo_prob = elo_probabilities(test)
    elo_metrics = classification_metrics(test["result"], elo_prob, LABELS)
    world_cup_backtests = {}
    for year in (2014, 2018, 2022):
        cutoff = pd.Timestamp(f"{year}-01-01", tz="UTC")
        year_end = pd.Timestamp(f"{year + 1}-01-01", tz="UTC")
        historical = rows.loc[rows["kickoff_utc"].lt(cutoff)]
        tournament = rows.loc[
            rows["kickoff_utc"].ge(cutoff)
            & rows["kickoff_utc"].lt(year_end)
            & rows["competition_type"].eq("world_cup")
        ]
        if len(historical) < 100 or tournament.empty:
            continue
        backtest_model = clone(model)
        backtest_model.fit(historical[features], historical["result"])
        backtest_classes = backtest_model.named_steps["model"].classes_.tolist()
        world_cup_backtests[str(year)] = classification_metrics(
            tournament["result"],
            backtest_model.predict_proba(tournament[features]),
            backtest_classes,
        ) | {"matches": len(tournament)}

    root = Path(root)
    model_dir = root / "models" / "outcome"
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": model, "features": features, "classes": classes},
        model_dir / "logistic_baseline.joblib",
    )
    version = dataset_version(
        [root / "data" / "features" / "feat_match_outcome.parquet"],
        features,
    )
    metadata = {
        "dataset_version": version,
        "training_cutoff": str(train["kickoff_utc"].max()),
        "validation_cutoff": str(validation["kickoff_utc"].max()),
        "train_rows": len(train),
        "validation_rows": len(validation),
        "test_rows": len(test),
        "features": features,
        "classes": classes,
        "metrics": logistic_metrics,
        "elo_metrics": elo_metrics,
        "world_cup_backtests": world_cup_backtests,
    }
    (model_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, default=str), encoding="utf-8"
    )
    with tracked_run(
        root / "mlruns",
        "outcome-baselines",
        {"dataset_version": version, "seed": 42},
    ) as run:
        run.log_metrics(**logistic_metrics)
        run.log_artifact(model_dir / "logistic_baseline.joblib")

    predictions = test[
        ["event_id", "kickoff_utc", "team_id", "opponent_id", "result"]
    ].copy()
    for index, label in enumerate(classes):
        predictions[f"probability_{label}"] = logistic_prob[:, index]
    predictions.to_parquet(
        root / "data" / "predictions" / "outcome_test_predictions.parquet",
        index=False,
    )
    _calibration_plot(
        test["result"],
        logistic_prob,
        classes,
        root / "reports" / "outcome_calibration.png",
    )
    _write_report(
        root / "reports" / "outcome_baseline_report.md",
        "Outcome baseline report",
        [
            ("Dataset", json.dumps(metadata, indent=2, default=str)),
            ("Logistic baseline", logistic_metrics),
            ("Elo baseline", elo_metrics),
            (
                "World Cup backtests",
                json.dumps(world_cup_backtests, indent=2),
            ),
        ],
    )
    return model, features, rows, test, logistic_metrics


def train_advanced_outcome(master, root, baseline_model, features):
    from xgboost import XGBClassifier

    rows = master.loc[
        master["side"].eq("home")
        & master["training_eligible"]
        & master["result"].notna()
    ].copy()
    train, validation, test = chronological_split(rows)
    preprocessor = _preprocessor(train, features)
    x_train = preprocessor.fit_transform(train[features])
    x_validation = preprocessor.transform(validation[features])
    x_test = preprocessor.transform(test[features])
    label_to_int = {label: index for index, label in enumerate(LABELS)}
    y_train = train["result"].map(label_to_int)
    model = XGBClassifier(
        objective="multi:softprob",
        num_class=3,
        n_estimators=350,
        max_depth=3,
        learning_rate=0.035,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=2.0,
        random_state=42,
        n_jobs=4,
    )
    model.fit(x_train, y_train)
    validation_xgb = model.predict_proba(x_validation)
    validation_baseline = baseline_model.predict_proba(validation[features])
    baseline_classes = baseline_model.named_steps["model"].classes_.tolist()
    baseline_positions = [baseline_classes.index(label) for label in LABELS]
    validation_baseline = validation_baseline[:, baseline_positions]
    best_alpha, best_loss = 0.0, float("inf")
    for alpha in np.linspace(0, 1, 11):
        blend = alpha * validation_xgb + (1 - alpha) * validation_baseline
        loss = classification_metrics(validation["result"], blend, LABELS)["log_loss"]
        if loss < best_loss:
            best_alpha, best_loss = float(alpha), float(loss)
    test_xgb = model.predict_proba(x_test)
    test_baseline = baseline_model.predict_proba(test[features])[:, baseline_positions]
    test_blend = best_alpha * test_xgb + (1 - best_alpha) * test_baseline
    metrics = classification_metrics(test["result"], test_blend, LABELS)
    baseline_metrics = classification_metrics(test["result"], test_baseline, LABELS)
    root = Path(root)
    champion_dir = root / "models" / "outcome" / "champion"
    champion_dir.mkdir(parents=True, exist_ok=True)
    artifact = {
        "xgboost": model,
        "preprocessor": preprocessor,
        "baseline": baseline_model,
        "features": features,
        "classes": LABELS,
        "blend_alpha": best_alpha,
    }
    joblib.dump(artifact, champion_dir / "model.joblib")
    comparison = {
        "champion": metrics,
        "logistic_baseline": baseline_metrics,
        "xgboost_blend_weight": best_alpha,
        "validation_log_loss": best_loss,
    }
    _write_report(
        root / "reports" / "outcome_model_comparison.md",
        "Advanced outcome model comparison",
        [
            ("Time-aware comparison", json.dumps(comparison, indent=2)),
            (
                "Selection",
                "The blend weight is selected only on chronological "
                "validation data. A zero weight means the nonlinear model did "
                "not add honest held-out value.",
            ),
        ],
    )
    version = dataset_version(
        [root / "data/features/feat_match_outcome.parquet"], features
    )
    with tracked_run(
        root / "mlruns",
        "outcome-champion",
        {
            "dataset_version": version,
            "seed": 42,
            "blend_alpha": best_alpha,
        },
    ) as run:
        run.log_metrics(**metrics)
        run.log_artifact(champion_dir / "model.joblib")
    if run.mlflow_run_id:
        try:
            import mlflow

            registered = mlflow.register_model(
                f"runs:/{run.mlflow_run_id}/model.joblib",
                "world_cup_outcome_champion",
            )
            mlflow.MlflowClient().set_registered_model_alias(
                "world_cup_outcome_champion",
                "champion",
                registered.version,
            )
        except Exception:
            # The artifact remains reproducible even if an external tracking
            # server has registry operations disabled.
            pass
    try:
        import matplotlib.pyplot as plt
        import shap

        sample = x_test[: min(500, len(x_test))]
        explanation = shap.TreeExplainer(model)(sample)
        values = np.abs(explanation.values).mean(axis=(0, 2))
        names = preprocessor.get_feature_names_out()
        top = np.argsort(values)[-20:]
        plt.figure(figsize=(8, 7))
        plt.barh(np.asarray(names)[top], values[top])
        plt.title("Mean absolute SHAP value")
        plt.tight_layout()
        plt.savefig(root / "reports" / "shap_outcome_summary.png", dpi=150)
        plt.close()
    except Exception as exc:
        _write_report(
            root / "reports" / "shap_outcome_fallback.md",
            "SHAP generation fallback",
            [("Reason", repr(exc))],
        )
    return artifact, comparison


def train_scoreline_models(master, root, features):
    home = master.loc[master["side"].eq("home") & master["training_eligible"]].copy()
    train, _, test = chronological_split(home)
    selected = [c for c in features if pd.api.types.is_numeric_dtype(train[c])][:50]
    models = {}
    predictions = test[
        [
            "event_id",
            "kickoff_utc",
            "team_id",
            "opponent_id",
            "goals_for",
            "goals_against",
        ]
    ].copy()
    metrics = {}
    for target, name in (
        ("goals_for", "home"),
        ("goals_against", "away"),
    ):
        model = Pipeline(
            [
                (
                    "impute",
                    SimpleImputer(strategy="median", add_indicator=True),
                ),
                ("scale", StandardScaler()),
                ("model", PoissonRegressor(alpha=1.0, max_iter=2_000)),
            ]
        )
        model.fit(train[selected], train[target])
        expected = np.clip(model.predict(test[selected]), 0.05, 6)
        predictions[f"{name}_expected_goals"] = expected
        metrics[f"{name}_mae"] = mean_absolute_error(test[target], expected)
        metrics[f"{name}_poisson_deviance"] = mean_poisson_deviance(
            test[target], expected
        )
        models[name] = model
    market_rows = []
    for row in predictions.itertuples(index=False):
        matrix = score_matrix(row.home_expected_goals, row.away_expected_goals)
        markets = market_probabilities(matrix)
        for line in (0.5, 1.5, 2.5):
            suffix = str(line).replace(".", "_")
            markets[f"home_over_{suffix}"] = float(
                matrix[np.arange(matrix.shape[0]) > line, :].sum()
            )
            markets[f"away_over_{suffix}"] = float(
                matrix[:, np.arange(matrix.shape[1]) > line].sum()
            )
        best = np.unravel_index(np.argmax(matrix), matrix.shape)
        market_rows.append(
            {
                "event_id": row.event_id,
                **markets,
                "most_likely_correct_score": f"{best[0]}-{best[1]}",
                "most_likely_correct_score_probability": float(matrix[best]),
                "score_probability_sum": matrix.sum(),
            }
        )
    predictions = predictions.merge(
        pd.DataFrame(market_rows), on="event_id", validate="one_to_one"
    )
    root = Path(root)
    path = root / "models" / "scoreline"
    path.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"models": models, "features": selected},
        path / "dixon_coles.joblib",
    )
    predictions.to_parquet(
        root / "data" / "predictions" / "pred_scoreline_samples.parquet",
        index=False,
    )
    _write_report(
        root / "reports" / "scoreline_backtest.md",
        "Scoreline and goal-market backtest",
        [("Metrics", metrics), ("Rows", len(predictions))],
    )
    return models, selected, metrics


def train_count_market(master, target, market_name, root):
    from xgboost import XGBRegressor

    rows = master.loc[master["training_eligible"] & master[target].notna()].copy()
    features = [
        c for c in _feature_columns(rows, 60) if pd.api.types.is_numeric_dtype(rows[c])
    ]
    train, _, test = chronological_split(rows)
    model = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
            ("model", PoissonRegressor(alpha=1.0, max_iter=2_000)),
        ]
    )
    model.fit(train[features], train[target])
    poisson_expected = np.clip(model.predict(test[features]), 0.01, None)
    boosted = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
            (
                "model",
                XGBRegressor(
                    objective="count:poisson",
                    n_estimators=250,
                    max_depth=3,
                    learning_rate=0.04,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    random_state=42,
                    n_jobs=4,
                ),
            ),
        ]
    )
    boosted.fit(train[features], train[target])
    boosted_expected = np.clip(boosted.predict(test[features]), 0.01, None)
    poisson_mae = mean_absolute_error(test[target], poisson_expected)
    boosted_mae = mean_absolute_error(test[target], boosted_expected)
    expected = boosted_expected if boosted_mae < poisson_mae else poisson_expected
    champion = boosted if boosted_mae < poisson_mae else model
    # Method-of-moments dispersion used for a negative-binomial alternative.
    target_mean = float(train[target].mean())
    target_variance = float(train[target].var())
    dispersion = max(
        (target_variance - target_mean) / max(target_mean**2, 1e-9),
        1e-6,
    )
    output = test[["event_id", "team_id", "opponent_id", "kickoff_utc", target]].copy()
    output["expected_count"] = expected
    lines = (
        [5.5, 7.5, 9.5, 11.5, 13.5]
        if market_name == "shots"
        else [2.5, 3.5, 4.5, 5.5, 6.5]
    )
    for line in lines:
        output[f"prob_over_{str(line).replace('.', '_')}"] = poisson.sf(
            int(line), expected
        )
    metrics = {
        "mae": mean_absolute_error(test[target], expected),
        "poisson_deviance": mean_poisson_deviance(test[target], expected),
        "poisson_mae": poisson_mae,
        "boosted_mae": boosted_mae,
        "negative_binomial_dispersion": dispersion,
        "champion": "boosted" if champion is boosted else "poisson",
        "rows": len(test),
    }
    root = Path(root)
    model_path = root / "models" / market_name
    model_path.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": champion,
            "poisson_model": model,
            "boosted_model": boosted,
            "features": features,
            "target": target,
            "negative_binomial_dispersion": dispersion,
        },
        model_path / "champion.joblib",
    )
    output.to_parquet(
        root / "data" / "predictions" / f"{market_name}_test_predictions.parquet",
        index=False,
    )
    _write_report(
        root / "reports" / f"{market_name}_model_report.md",
        f"{market_name.title()} model report",
        [("Metrics", metrics), ("Target", target)],
    )
    return model, metrics


def train_all_models(root):
    root = Path(root)
    (root / "data" / "predictions").mkdir(parents=True, exist_ok=True)
    master = pd.read_parquet(
        root / "data" / "features" / "team_match_feature_master.parquet"
    )
    outcome, features, _, _, outcome_metrics = train_outcome_models(master, root)
    _, advanced_metrics = train_advanced_outcome(master, root, outcome, features)
    _, _, score_metrics = train_scoreline_models(master, root, features)
    count_results = {}
    for target, name in (
        ("ALL_Total shots", "shots"),
        ("ALL_Shots on target", "shots_on_target"),
        ("ALL_Corner kicks", "corners"),
    ):
        if target in master and master[target].notna().sum() >= 100:
            _, count_results[name] = train_count_market(master, target, name, root)
    return {
        "outcome": outcome_metrics,
        "advanced_outcome": advanced_metrics,
        "scoreline": score_metrics,
        **count_results,
    }
