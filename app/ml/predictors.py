# app/ml/predictors.py

import os
import logging
from flask import current_app
import pandas as pd
import joblib
import shap
from sklearn.metrics import r2_score
from sklearn.ensemble import  RandomForestRegressor
from sklearn.model_selection import train_test_split
from app.ml.model_utils import load_model
from app.ml.model_utils import load_model
from app.ml.dataset_manager import PREPROCESSOR_PATH, PROCESSED_FEATURE_NAMES_PATH, TARGET_FEATURE, load_preprocessor, NUMERICAL_FEATURES, CATEGORICAL_FEATURES

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.getcwd(), "app", "ml", "models")

GLOBAL_PREPROCESSOR_EXCLUDED_COLS = ['student_id']


def generate_recommendations(feature_contributions: pd.Series) -> list:
    """Generates recommendations based on feature contributions."""
    recommendations = []
    # Sort by absolute SHAP value to prioritize most impactful features
    top_contributions = feature_contributions.abs().sort_values(ascending=False).head(5)

    for feature in top_contributions.index:
        contribution = feature_contributions[feature]
        if contribution > 0:
            # Positive contribution pushes towards dropout
            if 'social_media' in feature:
                recommendations.append("Consider reducing time spent on social media to improve focus and well-being.")
            elif 'mental_health_score' in feature:
                recommendations.append("Seeking mental health support or wellness counseling could be beneficial.")
            elif 'part_time_job_Yes' == feature:
                recommendations.append("Review your part-time work schedule to ensure it doesn't conflict with your studies.")
        elif contribution < 0:
            # Negative contribution pushes away from dropout
            if 'currentGPA' in feature or 'highSchoolGPA' in feature:
                recommendations.append("You are doing well academically. Continue to focus on your studies to maintain your GPA.")
            elif 'study_hours' in feature:
                recommendations.append("Increasing your dedicated study hours could further reduce your risk.")
            elif 'attendance' in feature:
                 recommendations.append("Your strong attendance is a positive factor. Keep this up.")

    # Add a general recommendation if no specific ones are generated
    if not recommendations:
        recommendations.append("Your current profile is well-balanced. Continue with your current academic and personal habits.")

    # Remove duplicates
    return list(dict.fromkeys(recommendations))

def predict(data: pd.DataFrame, model_name: str) -> tuple:
    data_for_prediction = data.copy()

    cols_to_drop = [col for col in ['studentName'] + GLOBAL_PREPROCESSOR_EXCLUDED_COLS + [TARGET_FEATURE] if col in data_for_prediction.columns]
    data_for_prediction.drop(columns=cols_to_drop, inplace=True, errors='ignore')

    try:
        model = joblib.load(model_name)
    except Exception as e:
        logger.error(f"Error loading model from {model_name}: {e}", exc_info=True)
        raise RuntimeError(f"Failed to load model from {model_name}") from e

    preprocessor, loaded_features = load_preprocessor(PREPROCESSOR_PATH, PROCESSED_FEATURE_NAMES_PATH)
    if preprocessor is None:
        raise ValueError("Preprocessor could not be loaded. Aborting prediction.")

    try:
        df_transformed = preprocessor.transform(data_for_prediction)
    except Exception as e:
        logger.error(f"Error transforming data with preprocessor: {e}", exc_info=True)
        raise RuntimeError(f"Failed to preprocess data: {e}") from e

    try:
        prediction_class = model.predict(df_transformed)[0]
        probabilities = model.predict_proba(df_transformed)[0] if hasattr(model, "predict_proba") else None

        # Create a SHAP explainer and get the SHAP values
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(df_transformed)
        
        # Get the SHAP values for the positive class (dropout)
        shap_values_class_1 = shap_values.flatten()

        # Combine feature names and SHAP values into a Series for easy analysis
        feature_contributions = pd.Series(shap_values_class_1, index=loaded_features)

        # Generate recommendations based on the feature contributions
        recommendations = generate_recommendations(feature_contributions)
        
        return prediction_class, probabilities, recommendations

    except Exception as e:
        logger.error(f"Error during model prediction: {e}", exc_info=True)
        raise RuntimeError(f"Failed to make prediction: {e}") from e

def predict_missing_fields(input_data: dict, dataset_name: str) -> dict:
    df_single_row = pd.DataFrame([input_data])

    imputed_data = df_single_row.copy()

    numeric_cols_in_input = df_single_row.select_dtypes(include=['int64', 'float64']).columns.tolist()

    for col_to_predict in numeric_cols_in_input:
        if imputed_data[col_to_predict].isnull().any():
            if col_to_predict in GLOBAL_PREPROCESSOR_EXCLUDED_COLS or col_to_predict == TARGET_FEATURE or col_to_predict == 'studentName':
                continue

            regression_model_path_lr = os.path.join(
                current_app.config['MODEL_DIR'],
                dataset_name,
                "lr",
                f"{col_to_predict}.pkl"
            ).replace("\\", "/")

            if os.path.exists(regression_model_path_lr):
                try:
                    regression_model = joblib.load(regression_model_path_lr)

                    X_reg_raw = imputed_data.drop(
                        columns=[col_to_predict] + GLOBAL_PREPROCESSOR_EXCLUDED_COLS + [TARGET_FEATURE],
                        errors='ignore'
                    ).copy()
                    
                    for col_reg in X_reg_raw.columns:
                        X_reg_raw[col_reg] = X_reg_raw[col_reg].apply(try_convert_float)
                    X_reg_raw = X_reg_raw.fillna(0)

                    if X_reg_raw.empty or X_reg_raw.shape[1] == 0:
                        imputed_data.at[0, col_to_predict] = 0
                        continue

                    predicted_value = regression_model.predict(X_reg_raw)[0]
                    imputed_data.at[0, col_to_predict] = predicted_value
                except Exception as e:
                    logger.warning(f"Error predicting missing {col_to_predict} using regression model: {e}. Falling back to 0.", exc_info=True)
                    imputed_data.at[0, col_to_predict] = 0
            else:
                logger.warning(f"Regression model for {col_to_predict} not found at {regression_model_path_lr}. Falling back to 0.")
                imputed_data.at[0, col_to_predict] = 0
                    
    return imputed_data.iloc[0].to_dict()

# try_convert_float helper function
def try_convert_float(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
