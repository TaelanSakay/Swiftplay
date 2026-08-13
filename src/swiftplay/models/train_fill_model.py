#!/usr/bin/env python3
"""
Train fill probability models (logistic regression and gradient boosting).

Loads labeled training data, trains both models, and compares performance.
Saves the best model and reports calibration metrics.
"""

import os
import pickle
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score, log_loss
from sklearn.preprocessing import StandardScaler


def calibration_check(y_true, y_pred_proba, n_bins=10):
    """
    Compute calibration metrics: bin predictions into deciles and compare
    predicted vs actual fill rate per bin.

    Returns mean absolute calibration error (MCE) and per-bin results.
    """
    bins = np.linspace(0, 1, n_bins + 1)
    bin_ids = np.digitize(y_pred_proba, bins) - 1
    bin_ids = np.clip(bin_ids, 0, n_bins - 1)

    calibration_results = []
    mce = 0.0
    n_nonempty_bins = 0

    for bin_id in range(n_bins):
        mask = bin_ids == bin_id
        if mask.sum() == 0:
            continue

        bin_preds = y_pred_proba[mask]
        bin_true = y_true[mask]

        predicted_mean = bin_preds.mean()
        actual_mean = bin_true.mean()

        calibration_results.append(
            {
                "bin": bin_id,
                "predicted": predicted_mean,
                "actual": actual_mean,
                "count": mask.sum(),
            }
        )
        mce += abs(predicted_mean - actual_mean)
        n_nonempty_bins += 1

    mce = mce / n_nonempty_bins if n_nonempty_bins > 0 else 0.0

    return mce, calibration_results


def train_models(
    data_path: str,
    output_dir: str = "src/swiftplay/models/artifacts",
) -> None:
    """
    Load training data, train logistic regression and gradient boosting,
    and save the better model.
    """
    os.makedirs(output_dir, exist_ok=True)

    print(f"Loading training data from {data_path}...")
    df = pd.read_csv(data_path)

    if df.empty:
        print("No training data found!")
        return

    print(f"Total examples: {len(df)}")

    feature_cols = ["microprice", "spread", "imbalance", "ofi", "realized_vol", "distance_from_mid"]

    X_all = df[feature_cols].values
    y_all = df["filled"].values

    # Time-based split: train on first 80%, test on last 20%
    split_idx = int(len(X_all) * 0.8)
    X_train, X_test = X_all[:split_idx], X_all[split_idx:]
    y_train, y_test = y_all[:split_idx], y_all[split_idx:]

    print(f"Train: {len(X_train)} examples, Test: {len(X_test)} examples")
    print(f"Class distribution in train: {y_train.mean():.3f} positive rate")
    print(f"Class distribution in test: {y_test.mean():.3f} positive rate")

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    print("\nTraining Logistic Regression...")
    lr_model = LogisticRegression(max_iter=1000, random_state=42)
    lr_model.fit(X_train_scaled, y_train)
    lr_preds = lr_model.predict_proba(X_test_scaled)[:, 1]
    lr_auc = roc_auc_score(y_test, lr_preds)
    lr_logloss = log_loss(y_test, lr_preds)
    lr_mce, lr_calib = calibration_check(y_test, lr_preds)

    print(f"  AUC: {lr_auc:.4f}")
    print(f"  Log Loss: {lr_logloss:.4f}")
    print(f"  Mean Calibration Error: {lr_mce:.4f}")

    print("\nTraining Gradient Boosting...")
    gb_model = GradientBoostingClassifier(n_estimators=100, random_state=42, max_depth=5)
    gb_model.fit(X_train_scaled, y_train)
    gb_preds = gb_model.predict_proba(X_test_scaled)[:, 1]
    gb_auc = roc_auc_score(y_test, gb_preds)
    gb_logloss = log_loss(y_test, gb_preds)
    gb_mce, gb_calib = calibration_check(y_test, gb_preds)

    print(f"  AUC: {gb_auc:.4f}")
    print(f"  Log Loss: {gb_logloss:.4f}")
    print(f"  Mean Calibration Error: {gb_mce:.4f}")

    print("\n=== Calibration Check (Logistic Regression) ===")
    print("Bin | Predicted | Actual | Count")
    for item in lr_calib:
        print(f"{item['bin']:2d}  | {item['predicted']:.3f}     | {item['actual']:.3f}  | {item['count']:4d}")

    print("\n=== Calibration Check (Gradient Boosting) ===")
    print("Bin | Predicted | Actual | Count")
    for item in gb_calib:
        print(f"{item['bin']:2d}  | {item['predicted']:.3f}     | {item['actual']:.3f}  | {item['count']:4d}")

    if gb_auc > lr_auc:
        print("\n✓ Gradient Boosting selected (higher AUC)")
        best_model = gb_model
        best_name = "gradient_boosting"
        best_auc = gb_auc
    else:
        print("\n✓ Logistic Regression selected (higher AUC)")
        best_model = lr_model
        best_name = "logistic_regression"
        best_auc = lr_auc

    model_path = os.path.join(output_dir, f"{best_name}_model.pkl")
    scaler_path = os.path.join(output_dir, "scaler.pkl")

    with open(model_path, "wb") as f:
        pickle.dump(best_model, f)
    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)

    print(f"\nModel saved to: {model_path}")
    print(f"Scaler saved to: {scaler_path}")

    summary = {
        "selected_model": best_name,
        "selected_auc": best_auc,
        "lr_auc": lr_auc,
        "gb_auc": gb_auc,
        "lr_logloss": lr_logloss,
        "gb_logloss": gb_logloss,
        "lr_mce": lr_mce,
        "gb_mce": gb_mce,
        "feature_names": feature_cols,
    }
    summary_path = os.path.join(output_dir, "model_summary.pkl")
    with open(summary_path, "wb") as f:
        pickle.dump(summary, f)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Train fill probability models")
    parser.add_argument(
        "--data",
        type=str,
        default="data/training/fill_labels.csv",
        help="Path to training data CSV",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="src/swiftplay/models/artifacts",
        help="Directory to save models",
    )
    args = parser.parse_args()

    train_models(args.data, args.output_dir)


if __name__ == "__main__":
    main()