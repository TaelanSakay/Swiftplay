#!/usr/bin/env python3
"""
TrainedFillProbabilityEstimator: ML-based fill probability prediction.

Loads a trained model and uses it as a drop-in replacement for the heuristic estimator.
"""

import os
import pickle
from pathlib import Path
import numpy as np
from swiftplay.decision.interfaces import FillProbabilityEstimator, MarketState
from swiftplay.features.pipeline import FeatureSnapshot


class TrainedFillProbabilityEstimator(FillProbabilityEstimator):
    """
    A trained ML model for fill probability estimation.
    Replaces the heuristic estimator with a logistic regression or gradient boosting model.
    """

    def __init__(self, model_dir: str = "src/swiftplay/models/artifacts"):
        self.model_dir = model_dir
        self.model = None
        self.scaler = None
        self.feature_names = [
            "microprice",
            "spread",
            "imbalance",
            "ofi",
            "imbalance_signed",
            "ofi_signed",
            "realized_vol",
            "distance_from_mid",
        ]

        self._load_model()

    def _load_model(self) -> None:
        """Load the trained model and scaler from artifacts."""
        model_summary_path = os.path.join(self.model_dir, "model_summary.pkl")
        if not os.path.exists(model_summary_path):
            raise FileNotFoundError(
                f"Model summary not found at {model_summary_path}. "
                f"Please run train_fill_model.py first."
            )

        with open(model_summary_path, "rb") as f:
            summary = pickle.load(f)

        model_name = summary["selected_model"]
        model_path = os.path.join(self.model_dir, f"{model_name}_model.pkl")
        scaler_path = os.path.join(self.model_dir, "scaler.pkl")

        with open(model_path, "rb") as f:
            self.model = pickle.load(f)
        with open(scaler_path, "rb") as f:
            self.scaler = pickle.load(f)

        print(f"Loaded {model_name} from {model_path}")

    def _signed_value(self, value: float, side: str) -> float:
        if side == "BUY":
            return value
        if side == "SELL":
            return -value
        return value

    def _feature_vector_for_side(
        self,
        state: MarketState,
        features: FeatureSnapshot,
        quote_price: float,
        side: str,
    ) -> dict[str, float]:
        if features.microprice is not None:
            ref_price = features.microprice
        else:
            ref_price = (state.bid_price + state.ask_price) / 2.0

        distance_from_mid = abs(quote_price - ref_price)
        imbalance_signed = self._signed_value(features.imbalance or 0.0, side)
        ofi_signed = self._signed_value(features.ofi, side)

        return {
            "microprice": features.microprice or ref_price,
            "spread": features.spread or 0.0,
            "imbalance": features.imbalance or 0.0,
            "ofi": features.ofi,
            "imbalance_signed": imbalance_signed,
            "ofi_signed": ofi_signed,
            "realized_vol": features.realized_vol or 0.0,
            "distance_from_mid": distance_from_mid,
        }

    def estimate(
        self,
        state: MarketState,
        features: FeatureSnapshot,
        quote_price: float,
        side: str,
    ) -> float:
        """
        Estimate fill probability using the trained model.
        """
        if self.model is None or self.scaler is None:
            return 0.5

        feature_dict = self._feature_vector_for_side(state, features, quote_price, side)
        feature_vector = np.array(
            [
                [
                    feature_dict["microprice"],
                    feature_dict["spread"],
                    feature_dict["imbalance"],
                    feature_dict["ofi"],
                    feature_dict["imbalance_signed"],
                    feature_dict["ofi_signed"],
                    feature_dict["realized_vol"],
                    feature_dict["distance_from_mid"],
                ]
            ]
        )

        feature_vector_scaled = self.scaler.transform(feature_vector)
        probability = self.model.predict_proba(feature_vector_scaled)[0, 1]
        return float(np.clip(probability, 0.0, 1.0))
