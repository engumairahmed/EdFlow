
import logging
import os
from flask import session
import pandas as pd
import joblib
import shap
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import f1_score, mean_squared_error, precision_score, r2_score, recall_score, roc_auc_score, accuracy_score
from datetime import datetime, timezone
import numpy as np
from sklearn.model_selection import train_test_split

from app import mongo
from app.ml.dataset_manager import CATEGORICAL_COLUMNS, PREPROCESSOR_PATH, REGRESSION_TARGETS_LIST, TARGET_FEATURE, build_preprocessor
from app.ml.model_utils import save_model

logger = logging.getLogger(__name__)

# MongoDB setup
db = mongo.db
metrics_collection = db['model_metrics']
trained_models_collection = db['trained_models']
datasets_collection = db['uploaded_datasets']  # NEW: collection for uploaded dataset

# Folder to store models
MODEL_DIR = 'app/ml/models'

# Columns to exclude
EXCLUDED_COLUMNS = ['student_id']

MODEL_PATHS = {
    "random_forest": os.path.join(MODEL_DIR, "rf_model.pkl"),
    "logistic_regression": os.path.join(MODEL_DIR, "lr_model.pkl"),
    "gradient_boosting": os.path.join(MODEL_DIR, "gb_model.pkl")
}

PROCESSED_FEATURE_NAMES_PATH = os.path.join(MODEL_DIR, 'processed_feature_names.pkl')
BACKGROUND_DATA_PATH = os.path.join(MODEL_DIR, 'shap_background_data.pkl')

def try_convert_float(value):
    try:
        return float(value)
    except:
        return np.nan

def train_dropout_models(df: pd.DataFrame, dataset_name: str):
    EXCLUDED_COLUMNS = [col for col in ['student_id'] if col in df.columns]
    X = df.drop(columns=[TARGET_FEATURE] + EXCLUDED_COLUMNS, errors='ignore')
    y = df[TARGET_FEATURE]

    preprocessor, processed_feature_names = build_preprocessor(X, target_to_exclude=TARGET_FEATURE)
    X_transformed = preprocessor.transform(X)

    try:
        joblib.dump(preprocessor, PREPROCESSOR_PATH)
        joblib.dump(processed_feature_names, PROCESSED_FEATURE_NAMES_PATH)
        logger.info(f"Main preprocessor and feature names saved to {PREPROCESSOR_PATH}")
    except Exception as e:
        logger.error(f"Error saving main preprocessor files: {e}", exc_info=True)

    if X_transformed.shape[0] > 500: # Adjust sample size based on dataset size and performance
        shap_background_data = shap.utils.sample(X_transformed, 500)
    else:
        shap_background_data = X_transformed

    try:
        joblib.dump(shap_background_data, BACKGROUND_DATA_PATH)
        logger.info(f"SHAP background data saved to {BACKGROUND_DATA_PATH}")
    except Exception as e:
        logger.error(f"Error saving SHAP background data to {BACKGROUND_DATA_PATH}: {e}", exc_info=True)


    models = {
        'random_forest': RandomForestClassifier(class_weight='balanced', random_state=42),
        'logistic_regression': LogisticRegression(max_iter=1000),
        'gradient_boosting': GradientBoostingClassifier()
    }

    model_results = []

    for name, model in models.items():
        try:
            X_train, X_test, y_train, y_test = train_test_split(X_transformed, y, test_size=0.2, random_state=42, stratify=y)
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            y_proba = model.predict_proba(X_test)[:, 1]

            model_dir = os.path.join(MODEL_DIR, dataset_name, name)
            os.makedirs(model_dir, exist_ok=True)
            model_path = os.path.join(model_dir, f"{TARGET_FEATURE}_{name}.pkl").replace("\\", "/")
            joblib.dump(model, model_path)

            model_results.append({
                "type": "classification",
                "target": TARGET_FEATURE,
                "model_name": name,
                "metrics": {
                    "accuracy": accuracy_score(y_test, y_pred),
                    "precision": precision_score(y_test, y_pred, zero_division=0),
                    "recall": recall_score(y_test, y_pred, zero_division=0),
                    "f1_score": f1_score(y_test, y_pred, zero_division=0),
                    "roc_auc": roc_auc_score(y_test, y_proba)
                },
                "model_path": model_path
            })

        except Exception as e:
            logger.error(f"Failed to train {name}: {e}")

    return model_results


def train_regression_models(df: pd.DataFrame, dataset_name: str):
    """
    Trains regression models for various features in the dataset.
    Each model gets its own preprocessor and is saved to a unique file path.
    """
    EXCLUDED_COLUMNS = [col for col in ['student_id'] if col in df.columns]
    df_cleaned = df.copy()
      
    # CRITICAL FIX: Only apply the float conversion to non-categorical columns
    numeric_cols_to_convert = [col for col in df_cleaned.columns if col not in EXCLUDED_COLUMNS + CATEGORICAL_COLUMNS]
    for col in numeric_cols_to_convert:
        if col in df_cleaned.columns:
            df_cleaned[col] = df_cleaned[col].apply(try_convert_float)
            
    # Convert categorical columns to the 'category' dtype for consistency
    for col in CATEGORICAL_COLUMNS:
        if col in df_cleaned.columns:
            df_cleaned[col] = df_cleaned[col].astype('category')

    regression_targets = REGRESSION_TARGETS_LIST
    dataset_dir = os.path.join(MODEL_DIR, dataset_name).replace("\\", "/")
    os.makedirs(dataset_dir, exist_ok=True)
    model_results = []
    
    for target in regression_targets:
        try:
            X = df_cleaned.drop(columns=[target] + EXCLUDED_COLUMNS, errors='ignore')
            y = df_cleaned[target]
            
            data_subset = pd.concat([X, y], axis=1).dropna(subset=[target])
            if len(data_subset) < 10:
                logger.warning(f"Insufficient data for regression on {target}. Skipping.")
                continue

            X_subset = data_subset.drop(columns=[target], errors='ignore')
            y_subset = data_subset[target]

            preprocessor, processed_feature_names = build_preprocessor(X_subset, target_to_exclude=target)
            X_transformed = preprocessor.transform(X_subset)

            preprocessor_path = os.path.join(dataset_dir, f"preprocessor_{target}.pkl").replace("\\", "/")
            features_path = os.path.join(dataset_dir, f"features_{target}.pkl").replace("\\", "/")

            # Save the preprocessor and feature names to their unique paths
            joblib.dump(preprocessor, preprocessor_path)
            joblib.dump(processed_feature_names, features_path)
            logger.info(f"Saved preprocessor and features for {target} to unique paths.")

            X_train, X_test, y_train, y_test = train_test_split(X_transformed, y_subset, test_size=0.2, random_state=42)

            # Linear Regression
            lr = LinearRegression()
            lr.fit(X_train, y_train)
            y_pred_lr = lr.predict(X_test)
            lr_model_dir = os.path.join(dataset_dir, "lr")
            os.makedirs(lr_model_dir, exist_ok=True)
            lr_model_path = os.path.join(lr_model_dir, f"{target}.pkl").replace("\\", "/")
            joblib.dump(lr, lr_model_path)
            logger.info(f"Trained and saved Linear Regression model for {target} to {lr_model_path}")

            model_results.append({
                "type": "regression",
                "target": target,
                "model_name": "linear_regression",
                "metrics": {
                    "mse": mean_squared_error(y_test, y_pred_lr),
                    "r2_score": r2_score(y_test, y_pred_lr)
                },
                "model_path": lr_model_path
            })

            # Random Forest Regressor
            rf = RandomForestRegressor(n_estimators=100, random_state=42)
            rf.fit(X_train, y_train)
            y_pred_rf = rf.predict(X_test)
            rf_model_dir = os.path.join(dataset_dir, "rf")
            os.makedirs(rf_model_dir, exist_ok=True)
            rf_model_path = os.path.join(rf_model_dir, f"{target}.pkl").replace("\\", "/")
            joblib.dump(rf, rf_model_path)
            logger.info(f"Trained and saved Random Forest Regressor model for {target} to {rf_model_path}")

            model_results.append({
                "type": "regression",
                "target": target,
                "model_name": "random_forest",
                "metrics": {
                    "mse": mean_squared_error(y_test, y_pred_rf),
                    "r2_score": r2_score(y_test, y_pred_rf)
                },
                "model_path": rf_model_path
            })

        except Exception as e:
            logger.error(f"Regression failed for {target}: {e}")

    return model_results

def train_all_models_and_save(df: pd.DataFrame, dataset_name: str, is_paid: bool):

    try:
        df[TARGET_FEATURE] = df[TARGET_FEATURE].replace({
            'Yes': 1, 'yes': 1,
            'No': 0, 'no': 0,
            True: 1,
            False: 0
        })        
        logger.info(f"Successfully converted '{TARGET_FEATURE}' column to 1/0 format.")

    except Exception as e:
        logger.warning(f"Error during conversion of '{TARGET_FEATURE}': {e}")

    classification_results = train_dropout_models(df, dataset_name)
    regression_results = train_regression_models(df, dataset_name)

    all_models = classification_results + regression_results

    try:
        # Assuming `trained_models_collection` is a MongoDB collection object
        trained_models_collection.insert_one({
            "dataset": dataset_name,
            "trained_by": {
                "userId": session["user_id"], # Ensure 'session' is accessible (from Flask context)
                "username": session["username"]
            },
            "created_at": datetime.now(timezone.utc),
            "is_paid": is_paid,
            "details": all_models
        })
        logger.info(f"Model training results saved to DB for dataset: {dataset_name}")
    except Exception as e:
        logger.error(f"Failed to save model training results to DB: {e}", exc_info=True)
    
    logger.info(f"Completed full model training for dataset: {dataset_name}")