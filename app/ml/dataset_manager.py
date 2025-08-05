# app/ml/dataset_manager.py

import logging
import os
from flask import current_app
import joblib
import pandas as pd
from hashlib import sha256

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder

from app.utils.mongodb_utils import delete_dataset_by_hash, insert_dataset

logger = logging.getLogger(__name__)

UPLOADS_DIR = os.path.join(os.getcwd(), "uploads")
MODEL_DIR = os.path.join(os.getcwd(), "app", "ml", "models")

NUMERICAL_FEATURES = [
    'age', 'study_hours', 'social_media_hours', 'netflix_hours',
    'attendance', 'sleep_hours', 'mental_health_score', 'exam_score',
    'highSchoolGPA', 'currentGPA'
]
CATEGORICAL_FEATURES = [
    'gender', 'diet_quality', 'exercise_frequency', 'parental_education',
    'internet_quality', 'part_time_job', 'extracurricular_activities'
]
TARGET_FEATURE = 'dropout'
EXCLUDED_COLUMNS = ['student_id']

REQUIRED_COLUMNS = NUMERICAL_FEATURES + CATEGORICAL_FEATURES + [TARGET_FEATURE] + EXCLUDED_COLUMNS

PREPROCESSOR_PATH = os.path.join(MODEL_DIR, 'preprocessor.pkl')

PROCESSED_FEATURE_NAMES_PATH = os.path.join(MODEL_DIR, 'processed_feature_names.pkl')

CATEGORICAL_COLUMNS = [
    'gender', 'part_time_job', 'diet_quality', 'exercise_frequency', 
    'parental_education', 'internet_quality', 'extracurricular_activities'
]

REGRESSION_TARGETS_LIST = [
    'age', 'highSchoolGPA', 'currentGPA', 'study_hours', 'social_media_hours', 
    'netflix_hours', 'attendance', 'sleep_hours', 'mental_health_score', 
    'exam_score'
]


def hash_dataframe(df: pd.DataFrame):
    structure_hash = sha256((",".join(df.columns)).encode()).hexdigest()
    return structure_hash

def validate_columns(df: pd.DataFrame) -> list:
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    return missing

def find_matching_dataset(new_df: pd.DataFrame):
    if not os.path.exists(UPLOADS_DIR):
        os.makedirs(UPLOADS_DIR)

    new_hash = hash_dataframe(new_df)
    for file_name in os.listdir(UPLOADS_DIR):
        if file_name.endswith(".csv"):
            existing_df = pd.read_csv(os.path.join(UPLOADS_DIR, file_name))
            existing_hash = hash_dataframe(existing_df)
            if new_hash == existing_hash:
                return os.path.join(UPLOADS_DIR, file_name)
    return None


def merge_with_existing_dataset(new_df, existing_file_path=None):
    if existing_file_path and os.path.exists(existing_file_path):
        existing_df = pd.read_csv(existing_file_path)
        merged_df = pd.concat([existing_df, new_df]).drop_duplicates().reset_index(drop=True)
        return merged_df
    else:
        return new_df


def save_dataset(df, file_path):
    df.to_csv(file_path, index=False)


def process_and_store_dataset(new_df):
    matched_file = find_matching_dataset(new_df)

    if matched_file:
        existing_df = pd.read_csv(matched_file)
        merged_df = pd.concat([existing_df, new_df]).drop_duplicates().reset_index(drop=True)

        new_file_index = len(os.listdir(UPLOADS_DIR)) + 1
        new_file_name = f"merged_dataset_{new_file_index}.csv"
        new_file_path = os.path.join(UPLOADS_DIR, new_file_name)

        save_dataset(merged_df, new_file_path)
        insert_dataset(merged_df, hash_dataframe(merged_df))

        return f"Dataset matched with {os.path.basename(matched_file)} and saved as new file {new_file_name}."

    else:
        file_name = f"dataset_{len(os.listdir(UPLOADS_DIR)) + 1}.csv"
        file_path = os.path.join(UPLOADS_DIR, file_name)
        save_dataset(new_df, file_path)
        insert_dataset(new_df, hash_dataframe(new_df))
        return f"New dataset saved as {file_name} and inserted in MongoDB."



def str_to_bool(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ['yes', 'true', '1']
    return False


def load_and_prepare_student_data():
    db = current_app.db
    students_data = list(db.students.find({}))
    if not students_data:
        logger.warning("No student data found in MongoDB for ML processing.")
        return pd.DataFrame()

    df = pd.DataFrame(students_data)

    for feature in NUMERICAL_FEATURES + CATEGORICAL_FEATURES:
        if feature in ['highSchoolGPA', 'currentGPA']:
            if feature not in df.columns:
                df[feature] = None
            continue

    if TARGET_FEATURE not in df.columns:
        df[TARGET_FEATURE] = False
        logger.warning(f"'{TARGET_FEATURE}' column not found in data, defaulting to False.")

    df_ml = df[NUMERICAL_FEATURES + CATEGORICAL_FEATURES + [TARGET_FEATURE]].copy()

    for col in ['part_time_job', 'extracurricular_activities']:
        if col in df_ml.columns:
            df_ml[col] = df_ml[col].apply(lambda x: str_to_bool(x) if pd.notna(x) else False)

    for col in NUMERICAL_FEATURES:
        if col in df_ml.columns and df_ml[col].isnull().any():
            mean_val = df_ml[col].mean()
            df_ml[col].fillna(mean_val, inplace=True)
            logger.info(f"Imputed missing values in '{col}' with mean: {mean_val:.2f}")

    for col in CATEGORICAL_FEATURES:
        if col in df_ml.columns and df_ml[col].isnull().any():
            df_ml[col].fillna('missing', inplace=True)
            logger.info(f"Imputed missing values in '{col}' with 'missing' category.")

    try:
        X = df_ml[NUMERICAL_FEATURES + CATEGORICAL_FEATURES]
        y = df_ml[TARGET_FEATURE]

        preprocessor = build_preprocessor()
        preprocessor.fit(X)
        X_processed = preprocessor.transform(X)

        feature_names = preprocessor.named_steps['preprocessor'].get_feature_names_out()
        df_processed = pd.DataFrame(X_processed, columns=feature_names, index=df_ml.index)
        df_processed[TARGET_FEATURE] = y

        joblib.dump(preprocessor, PREPROCESSOR_PATH)
        logger.info(f"Preprocessor saved to {PREPROCESSOR_PATH}")

        logger.info(f"Data loaded and preprocessed. Shape: {df_processed.shape}")
        return df_processed

    except Exception as e:
        logger.error(f"Error during data preprocessing: {e}", exc_info=True)
        return pd.DataFrame()

def get_feature_names_after_preprocessing(preprocessor: ColumnTransformer) -> list:
    """
    Helper function to get feature names after preprocessing, including one-hot encoded names.
    """
    feature_names = []
    for name, transformer, columns in preprocessor.transformers_:
        if name == 'num':
            # Numeric features are simply the column names
            feature_names.extend(columns)
        elif name == 'cat':
            # Get one-hot encoded feature names
            onehot_features = transformer.named_steps['onehot'].get_feature_names_out(columns)
            feature_names.extend(onehot_features)
    return feature_names


def build_preprocessor(X: pd.DataFrame, target_to_exclude: str) -> tuple[ColumnTransformer, list]:

    logger.info("Building preprocessor...")
    
    numeric_features = X.select_dtypes(include=['int64', 'float64']).columns.tolist()
    categorical_features = X.select_dtypes(include=['object', 'bool', 'category']).columns.tolist()
    
    if target_to_exclude in numeric_features:
        numeric_features.remove(target_to_exclude)
    if target_to_exclude in categorical_features:
        categorical_features.remove(target_to_exclude)

    numeric_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='mean')),
        ('scaler', StandardScaler())
    ])

    categorical_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
        ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', numeric_transformer, numeric_features),
            ('cat', categorical_transformer, categorical_features)
        ],
        remainder='passthrough'
    )

    preprocessor.fit(X)
    processed_feature_names = get_feature_names_after_preprocessing(preprocessor)
    
    logger.info("Preprocessor built and fitted successfully.")
    
    return preprocessor, processed_feature_names


def load_preprocessor(preprocessor_path: str, features_path: str) -> tuple[ColumnTransformer | None, list | None]:

    preprocessor = None
    processed_feature_names = None
    
    if os.path.exists(preprocessor_path):
        try:
            preprocessor = joblib.load(preprocessor_path)
            logger.info(f"Preprocessor loaded from {preprocessor_path}")
        except Exception as e:
            logger.error(f"Error loading preprocessor from {preprocessor_path}: {e}", exc_info=True)
            preprocessor = None
    else:
        logger.warning(f"No preprocessor found at {preprocessor_path}.")

    if os.path.exists(features_path):
        try:
            processed_feature_names = joblib.load(features_path)
            logger.info(f"Processed feature names loaded from {features_path}")
        except Exception as e:
            logger.error(f"Error loading processed feature names from {features_path}: {e}", exc_info=True)
            processed_feature_names = None
    else:
        logger.warning(f"No processed feature names found at {features_path}.")

    return preprocessor, processed_feature_names
