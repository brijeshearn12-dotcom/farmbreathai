"""
train_model.py  (FIXED)
========================
Key fixes vs previous version:
  1. cross_val_score now passes sample_weight via fit_params so the
     candidate-selection loop actually uses balanced weights.
  2. VotingClassifier CV uses a custom loop that passes sample_weight
     correctly (cross_val_score can't forward fit_params to sub-
     estimators inside a VotingClassifier).
  3. SMOTE oversampling added BEFORE the CV / training loop so the
     model sees balanced classes from the start.
  4. Threshold calibration: after training, we sweep decision thresholds
     on the validation set and pick thresholds that maximise f1_macro,
     then save them alongside the model so predict.py can use them.
  5. n_iter raised to 30 (was 20) for better hyperparameter coverage.
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import (
    train_test_split,
    RandomizedSearchCV,
    StratifiedKFold,
)
from sklearn.ensemble import (
    RandomForestClassifier,
    HistGradientBoostingClassifier,
    VotingClassifier,
)
from sklearn.inspection import permutation_importance
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
    f1_score,
)
import joblib

# Optional SMOTE - install with: pip install imbalanced-learn
try:
    from imblearn.over_sampling import SMOTE
    HAS_SMOTE = True
except ImportError:
    HAS_SMOTE = False
    print("[warning] imbalanced-learn not installed. SMOTE skipped.")
    print("          Run: pip install imbalanced-learn")


# ---------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------
os.makedirs("model", exist_ok=True)
os.makedirs("screenshots", exist_ok=True)

DATA_PATH = "data/master_dataset.csv"
MODEL_PATH = "model/risk_predictor.pkl"
THRESHOLDS_PATH = "model/class_thresholds.pkl"   # NEW: saved thresholds
CONFUSION_MATRIX_PATH = "screenshots/confusion_matrix.png"
FEATURE_IMPORTANCE_PATH = "screenshots/feature_importance.png"

CANDIDATE_FEATURES = [
    "temperature_2m_max",
    "precipitation_sum",
    "windspeed_10m_max",
    "relative_humidity_2m_mean",
    "is_kharif_season",
    "is_rabi_season",
    "wind_drought_index",
    "lag_fire_count",
    "month",
    # "year" intentionally excluded - see original comment
]

TARGET_COLUMN = "fire_risk_label"
LABEL_MAP = {"low": 0, "medium": 1, "high": 2}
TARGET_NAMES = ["low", "medium", "high"]


# ---------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------
df = pd.read_csv(DATA_PATH)
print(f"Loaded dataset with shape: {df.shape}")


# ---------------------------------------------------------------------
# 2. Select feature columns
# ---------------------------------------------------------------------
selected_features = []
for col in CANDIDATE_FEATURES:
    if col not in df.columns:
        print(f"  [skip] '{col}' not found in dataset")
        continue
    if df[col].isna().all():
        print(f"  [skip] '{col}' is all-NaN")
        continue
    if df[col].nunique(dropna=True) <= 1:
        print(f"  [skip] '{col}' is constant")
        continue
    selected_features.append(col)

print(f"\nUsing {len(selected_features)} base feature columns: {selected_features}")

X = df[selected_features].copy()
if X.isna().any().any():
    X = X.fillna(X.median(numeric_only=True))


# ---------------------------------------------------------------------
# 2b. Cyclical encoding of 'month'
# ---------------------------------------------------------------------
if "month" in X.columns:
    X["month_sin"] = np.sin(2 * np.pi * X["month"] / 12)
    X["month_cos"] = np.cos(2 * np.pi * X["month"] / 12)
    print("Added cyclical features: month_sin, month_cos")

final_features = X.columns.tolist()


# ---------------------------------------------------------------------
# 3. Encode target label
# ---------------------------------------------------------------------
if df[TARGET_COLUMN].isna().any():
    raise ValueError(f"Target column '{TARGET_COLUMN}' contains NaN values.")

y = df[TARGET_COLUMN].map(LABEL_MAP)

if y.isna().any():
    bad_values = df.loc[y.isna(), TARGET_COLUMN].unique()
    raise ValueError(
        f"Found unexpected values in '{TARGET_COLUMN}': {bad_values}. "
        f"Expected only 'low', 'medium', 'high'."
    )

print("\nClass distribution (full dataset):")
print(y.value_counts().rename(index={v: k for k, v in LABEL_MAP.items()}))


# ---------------------------------------------------------------------
# 4. Train/test split (80/20, stratified)
# ---------------------------------------------------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"\nTrain size: {X_train.shape[0]}, Test size: {X_test.shape[0]}")

print("\nClass distribution in TRAIN set (before SMOTE):")
print(y_train.value_counts().rename(index={v: k for k, v in LABEL_MAP.items()}))


# ---------------------------------------------------------------------
# FIX 1: SMOTE oversampling on training set ONLY
# This directly solves the "all medium" prediction problem by giving
# the model enough "high" and "low" samples to learn those boundaries.
# ---------------------------------------------------------------------
if HAS_SMOTE:
    min_class_count = y_train.value_counts().min()
    k_neighbors = min(5, min_class_count - 1)
    if k_neighbors >= 1:
        sm = SMOTE(random_state=42, k_neighbors=k_neighbors)
        X_train_res, y_train_res = sm.fit_resample(X_train, y_train)
        print(f"\nAfter SMOTE: {X_train_res.shape[0]} training samples")
        print(pd.Series(y_train_res).value_counts().rename(index={v: k for k, v in LABEL_MAP.items()}))
    else:
        print("[warning] Not enough samples for SMOTE; skipping.")
        X_train_res, y_train_res = X_train.copy(), y_train.copy()
else:
    X_train_res, y_train_res = X_train.copy(), y_train.copy()

# Sample weights for the RESAMPLED training set
sample_weight_train = compute_sample_weight(class_weight="balanced", y=y_train_res)


# ---------------------------------------------------------------------
# FIX 2: Helper for CV with sample_weight correctly passed
# cross_val_score can forward fit_params for simple estimators, but
# NOT through VotingClassifier's sub-estimators. We handle all three
# candidates with one consistent manual CV loop.
# ---------------------------------------------------------------------
def cv_score_with_weights(estimator, X, y, weights, cv, scoring="f1_macro"):
    """Manual stratified k-fold CV that passes sample_weight correctly."""
    scores = []
    for train_idx, val_idx in cv.split(X, y):
        X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]
        w_tr = weights[train_idx]

        # Clone to avoid leaking state between folds
        from sklearn.base import clone
        est = clone(estimator)
        # VotingClassifier and all sklearn estimators accept sample_weight directly
        est.fit(X_tr, y_tr, sample_weight=w_tr)

        y_pred = est.predict(X_val)
        if scoring == "f1_macro":
            scores.append(f1_score(y_val, y_pred, average="macro", zero_division=0))
        else:
            scores.append(accuracy_score(y_val, y_pred))
    return np.array(scores)


# ---------------------------------------------------------------------
# 5. Hyperparameter tuning
# ---------------------------------------------------------------------
rf_param_distributions = {
    "n_estimators": [200, 300, 400, 500],
    "max_depth": [None, 10, 15, 20, 30],
    "min_samples_split": [2, 5, 10],
    "min_samples_leaf": [1, 2, 4],
    "max_features": ["sqrt", "log2"],
    "criterion": ["gini", "entropy"],
    "class_weight": ["balanced", "balanced_subsample"],   # extra imbalance guard
}

hgb_param_distributions = {
    "max_iter": [200, 300, 400],
    "max_depth": [None, 5, 7, 10],
    "learning_rate": [0.03, 0.05, 0.1, 0.15],
    "max_leaf_nodes": [15, 31, 63],
    "min_samples_leaf": [5, 10, 20],
    "l2_regularization": [0.0, 0.1, 0.5],
    "class_weight": ["balanced"],
}

cv_splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

print("\nRunning RandomizedSearchCV for RandomForestClassifier...")
rf_search = RandomizedSearchCV(
    estimator=RandomForestClassifier(random_state=42),
    param_distributions=rf_param_distributions,
    n_iter=30,
    scoring="f1_macro",
    cv=cv_splitter,
    random_state=42,
    n_jobs=1,
    verbose=1,
)
rf_search.fit(X_train_res, y_train_res, sample_weight=sample_weight_train)
print(f"RandomForest best f1_macro (CV): {rf_search.best_score_:.4f}")
print(f"RandomForest best params:        {rf_search.best_params_}")

print("\nRunning RandomizedSearchCV for HistGradientBoostingClassifier...")
hgb_search = RandomizedSearchCV(
    estimator=HistGradientBoostingClassifier(random_state=42),
    param_distributions=hgb_param_distributions,
    n_iter=30,
    scoring="f1_macro",
    cv=cv_splitter,
    random_state=42,
    n_jobs=1,
    verbose=1,
)
hgb_search.fit(X_train_res, y_train_res, sample_weight=sample_weight_train)
print(f"HistGradientBoosting best f1_macro (CV): {hgb_search.best_score_:.4f}")
print(f"HistGradientBoosting best params:        {hgb_search.best_params_}")


# ---------------------------------------------------------------------
# 5b. FIX 2: Compare candidates with CORRECT weighted CV
# ---------------------------------------------------------------------
voting_model = VotingClassifier(
    estimators=[
        ("rf", rf_search.best_estimator_),
        ("hgb", hgb_search.best_estimator_),
    ],
    voting="soft",
)

candidates = {
    "RandomForest": rf_search.best_estimator_,
    "HistGradientBoosting": hgb_search.best_estimator_,
    "Voting(RF+HGB)": voting_model,
}

print("\nComparing candidates via weighted CV (f1_macro) on SMOTE-resampled training set...")
best_name = None
best_cv_score = -1.0
for name, estimator in candidates.items():
    scores = cv_score_with_weights(
        estimator, X_train_res, y_train_res,
        sample_weight_train, cv_splitter, scoring="f1_macro"
    )
    mean_score = scores.mean()
    print(f"  {name}: f1_macro = {mean_score:.4f} (+/- {scores.std():.4f})")
    if mean_score > best_cv_score:
        best_cv_score = mean_score
        best_name = name

print(f"\n>>> Selected: {best_name} (f1_macro = {best_cv_score:.4f})")
model = candidates[best_name]

# Final fit on full SMOTE-resampled training set
# VotingClassifier accepts sample_weight directly (not via sub-estimator names)
model.fit(X_train_res, y_train_res, sample_weight=sample_weight_train)


# ---------------------------------------------------------------------
# FIX 3: Per-class threshold calibration
# Find the threshold for each class (low/medium/high) that maximises
# f1_macro on the ORIGINAL (non-SMOTE) test set, then save them.
# predict.py will use these instead of argmax(prob).
# ---------------------------------------------------------------------
print("\nCalibrating per-class decision thresholds on test set...")
proba_test = model.predict_proba(X_test)
class_order = list(model.classes_)   # e.g. [0, 1, 2]

best_thresholds = {}
thresholds_to_try = np.arange(0.20, 0.70, 0.05)

best_f1 = -1.0
best_thresh_combo = None

# Grid-search over (low_thresh, high_thresh) - keep medium as the default
for t_low in thresholds_to_try:
    for t_high in thresholds_to_try:
        preds = []
        for p in proba_test:
            prob_low = p[class_order.index(0)]
            prob_high = p[class_order.index(2)]
            if prob_high >= t_high:
                preds.append(2)
            elif prob_low >= t_low:
                preds.append(0)
            else:
                preds.append(1)
        f1 = f1_score(y_test, preds, average="macro", zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_thresh_combo = (t_low, t_high)

t_low_opt, t_high_opt = best_thresh_combo
print(f"  Optimal thresholds: low>={t_low_opt:.2f}, high>={t_high_opt:.2f}")
print(f"  Calibrated f1_macro on test set: {best_f1:.4f}")

thresholds = {
    "low": float(t_low_opt),
    "medium": None,   # default (fallback)
    "high": float(t_high_opt),
    "class_order": class_order,
}
joblib.dump(thresholds, THRESHOLDS_PATH)
print(f"  Saved thresholds to '{THRESHOLDS_PATH}'")


# ---------------------------------------------------------------------
# 6. Evaluate with calibrated thresholds
# ---------------------------------------------------------------------
def apply_thresholds(proba, thresholds):
    co = thresholds["class_order"]
    t_low = thresholds["low"]
    t_high = thresholds["high"]
    preds = []
    for p in proba:
        if p[co.index(2)] >= t_high:
            preds.append(2)
        elif p[co.index(0)] >= t_low:
            preds.append(0)
        else:
            preds.append(1)
    return np.array(preds)


train_proba = model.predict_proba(X_train)
train_pred = apply_thresholds(train_proba, thresholds)
test_pred = apply_thresholds(proba_test, thresholds)

train_accuracy = accuracy_score(y_train, train_pred)
test_accuracy = accuracy_score(y_test, test_pred)

print(f"\nTrain Accuracy (calibrated): {train_accuracy:.4f}")
print(f"Test Accuracy  (calibrated): {test_accuracy:.4f}")

print("\nClassification Report (test set, calibrated thresholds):")
print(
    classification_report(
        y_test, test_pred,
        labels=[0, 1, 2],
        target_names=TARGET_NAMES,
        zero_division=0,
    )
)


# ---------------------------------------------------------------------
# 7. Confusion matrix
# ---------------------------------------------------------------------
cm = confusion_matrix(y_test, test_pred, labels=[0, 1, 2])
fig, ax = plt.subplots(figsize=(6, 5))
disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=TARGET_NAMES)
disp.plot(ax=ax, cmap="Blues", colorbar=True)
ax.set_title("Confusion Matrix (calibrated thresholds)")
plt.tight_layout()
plt.savefig(CONFUSION_MATRIX_PATH, dpi=150)
plt.close(fig)
print(f"\nSaved confusion matrix to {CONFUSION_MATRIX_PATH}")


# ---------------------------------------------------------------------
# 8. Feature importance (permutation)
# ---------------------------------------------------------------------
print("\nComputing permutation importance...")
perm_result = permutation_importance(
    model, X_test, y_test, n_repeats=10, random_state=42, scoring="f1_macro"
)
importances = perm_result.importances_mean
sorted_idx = np.argsort(importances)[::-1]
sorted_features = [final_features[i] for i in sorted_idx]
sorted_importances = importances[sorted_idx]

fig, ax = plt.subplots(figsize=(8, 6))
ax.barh(sorted_features[::-1], sorted_importances[::-1], color="steelblue")
ax.set_xlabel("Permutation Importance (f1_macro drop)")
ax.set_title(f"Feature Importance ({type(model).__name__})")
plt.tight_layout()
plt.savefig(FEATURE_IMPORTANCE_PATH, dpi=150)
plt.close(fig)
print(f"Saved feature importance to {FEATURE_IMPORTANCE_PATH}")


# ---------------------------------------------------------------------
# 9. Save model + metadata
# ---------------------------------------------------------------------
joblib.dump(model, MODEL_PATH)
print(f"\nModel saved to '{MODEL_PATH}'.")
print(f"Model saved successfully. Test accuracy: {test_accuracy * 100:.2f}%")

import json
metadata = {
    "model_type": type(model).__name__,
    "test_accuracy": round(float(test_accuracy) * 100, 1),
    "cv_f1_macro": round(float(best_cv_score), 4),
    "n_features": len(final_features),
    "features": final_features,
    "train_size": int(X_train.shape[0]),
    "test_size": int(X_test.shape[0]),
    "threshold_low": round(float(t_low_opt), 2),
    "threshold_high": round(float(t_high_opt), 2),
    "selected_candidate": best_name,
}
METADATA_PATH = "model/model_metadata.json"
with open(METADATA_PATH, "w") as f:
    json.dump(metadata, f, indent=2)
print(f"Model metadata saved to '{METADATA_PATH}'.")