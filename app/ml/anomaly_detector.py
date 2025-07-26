# app/ml/anomaly_detector.py

import pandas as pd
from sklearn.ensemble import IsolationForest
import os

# Assuming merged_dataset_2.csv is in the 'uploads' directory relative to the project root
# Make sure your 'uploads' directory is at the same level as 'app' folder
UPLOADS_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)), 'uploads')
DATA_FILE_PATH = os.path.join(UPLOADS_DIR, 'merged_dataset_2.csv')

def detect_student_anomalies(n_estimators=100, contamination=0.05, random_state=42):
    """
    Detects anomalies in student data using Isolation Forest.

    Args:
        n_estimators (int): The number of base estimators in the ensemble.
        contamination (float or 'auto'): The amount of contamination of the dataset,
                                       i.e. the proportion of outliers in the dataset.
                                       Used when fitting to define the threshold on the scores of the samples.
        random_state (int): Controls the pseudo-randomness of the estimator.

    Returns:
        pd.DataFrame: Original DataFrame with an added 'is_anomaly' column (1 for anomaly, -1 for normal)
                      and 'anomaly_score' column.
        list: List of dictionaries for anomalous students.
    """
    if not os.path.exists(DATA_FILE_PATH):
        print(f"Error: Data file not found at {DATA_FILE_PATH}. Please ensure 'merged_dataset_2.csv' is in the 'uploads' directory.")
        return pd.DataFrame(), [] # Return empty DataFrame and list if file is not found

    try:
        df = pd.read_csv(DATA_FILE_PATH)
    except Exception as e:
        print(f"Error reading CSV file at {DATA_FILE_PATH}: {e}")
        return pd.DataFrame(), []

    # Select features for anomaly detection based on merged_dataset_2.csv's likely columns
    # These were chosen based on relevancy for student performance/behavior anomalies
    features = [
        'attendance_percentage',
        'study_hours_per_day',
        'exam_score',
        'social_media_hours',
        'sleep_hours',
        'mental_health_rating'
    ]

    # Filter out features that are not in the DataFrame
    available_features = [f for f in features if f in df.columns]
    print(available_features)
    if len(available_features) < 2: # Need at least 2 features for meaningful detection
        print(f"Error: Not enough relevant features found in the dataset. Available: {available_features}")
        return pd.DataFrame(), []

    # Drop rows with any missing values in the selected features for simplicity
    df_processed = df.dropna(subset=available_features).copy()

    # Check if df_processed is empty after dropping NaNs
    if df_processed.empty:
        print("Warning: No valid data after dropping rows with missing values in selected features.")
        return pd.DataFrame(), []

    # Convert relevant columns to numeric, coercing errors to NaN
    for col in available_features:
        df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce')
    print(df_processed)
    # Drop any rows that became NaN after numeric conversion
    df_processed.dropna(subset=available_features, inplace=True)
    print(df_processed)
    if df_processed.empty:
        print("Warning: No valid data after numeric conversion and dropping NaNs.")
        return pd.DataFrame(), []

    X = df_processed[available_features]

    # Initialize and train Isolation Forest model
    model = IsolationForest(n_estimators=n_estimators, contamination=contamination, random_state=random_state)
    model.fit(X)

    # Predict anomalies (-1 for outliers, 1 for inliers)
    df_processed['is_anomaly'] = model.predict(X)

    # Get anomaly scores (lower score indicates higher anomaly likelihood)
    df_processed['anomaly_score'] = model.decision_function(X)

    # Filter for anomalous students
    anomalous_students_df = df_processed[df_processed['is_anomaly'] == -1]

    # Prepare data for display in Flask template
    # Ensure all original columns needed for display are included, plus new anomaly columns
    anomalous_students_list = anomalous_students_df.to_dict(orient='records')

    return df_processed, anomalous_students_list