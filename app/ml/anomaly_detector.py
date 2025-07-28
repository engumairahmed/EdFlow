# app/ml/anomaly_detector.py

import pandas as pd
from sklearn.ensemble import IsolationForest
import os
import numpy as np

# UPLOADS_DIR ko ab bhi define karenge, lekin DATA_FILE_PATH ko function ke andar decide karenge
UPLOADS_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)), 'uploads')

def detect_student_anomalies(file_name, n_estimators=100, contamination=0.05, random_state=42): # file_name argument add kiya
    """
    Detects anomalies in student data using Isolation Forest, including categorical feature handling
    and identifying contributing features for anomalies.

    Args:
        file_name (str): The name of the CSV file to process from the 'uploads' directory.
        n_estimators (int): The number of base estimators in the ensemble.
        contamination (float or 'auto'): The amount of contamination of the dataset,
                                       i.e. the proportion of outliers in the dataset.
        random_state (int): Controls the pseudo-randomness of the estimator.

    Returns:
        pd.DataFrame: Original DataFrame with an added 'is_anomaly' column (1 for anomaly, -1 for normal)
                      and 'anomaly_score' column.
        list: List of dictionaries for anomalous students, each including 'extreme_features'.
    """
    DATA_FILE_PATH = os.path.join(UPLOADS_DIR, file_name) # Ab file_name use karenge

    if not os.path.exists(DATA_FILE_PATH):
        print(f"Error: Data file not found at {DATA_FILE_PATH}.")
        return pd.DataFrame(), []

    try:
        df = pd.read_csv(DATA_FILE_PATH)
    except Exception as e:
        print(f"Error reading CSV file at {DATA_FILE_PATH}: {e}")
        return pd.DataFrame(), []

    # Define numerical and categorical features expected in your dataset
    numerical_cols = [
        'age',
        'attendance_percentage',
        'study_hours_per_day',
        'exam_score',
        'social_media_hours',
        'sleep_hours',
        'mental_health_rating',
        'netflix_hours',
        'exercise_frequency'
    ]
    
    categorical_cols = [
        'gender',
        'part_time_job',
        'diet_quality',
        'parental_education_level',
        'internet_quality',
        'extracurricular_participation'
    ]

    # Filter features based on what's actually in the DataFrame
    numerical_features_in_df = [col for col in numerical_cols if col in df.columns]
    categorical_features_in_df = [col for col in categorical_cols if col in df.columns]

    df_processed = df.copy()

    # Process Numerical Features: Convert to numeric and impute NaNs
    for col in numerical_features_in_df:
        df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce')
        # Impute NaNs with the median of the column
        if df_processed[col].isnull().any():
            median_val = df_processed[col].median()
            df_processed[col].fillna(median_val, inplace=True)

    # Process Categorical Features: Fill NaNs and One-Hot Encode
    for col in categorical_features_in_df:
        if df_processed[col].isnull().any():
            df_processed[col].fillna('Unknown', inplace=True)
    
    if categorical_features_in_df:
        df_processed = pd.get_dummies(df_processed, columns=categorical_features_in_df, drop_first=True, dtype=int)

    # Define the final set of features to be used by Isolation Forest
    model_features = numerical_features_in_df + [col for col in df_processed.columns if any(col.startswith(cat_col + '_') for cat_col in categorical_features_in_df)]
    
    final_model_features = []
    for f in model_features:
        if f in df_processed.columns and pd.api.types.is_numeric_dtype(df_processed[f]):
            final_model_features.append(f)
        else:
            print(f"Warning: Feature '{f}' could not be converted to numeric or is missing after processing and will be excluded from the model.")

    if len(final_model_features) < 2:
        print(f"Error: Not enough valid numerical features for anomaly detection after preprocessing. Found: {final_model_features}")
        return pd.DataFrame(), []

    X = df_processed[final_model_features]

    # Initialize and train Isolation Forest model
    model = IsolationForest(n_estimators=n_estimators, contamination=contamination, random_state=random_state)
    model.fit(X)

    # Predict anomalies (-1 for outliers, 1 for inliers)
    df_processed['is_anomaly'] = model.predict(X)
    df['is_anomaly'] = df_processed['is_anomaly'] # Add to original df for tracking

    # Get raw anomaly scores
    df_processed['anomaly_score'] = model.decision_function(X)
    df['anomaly_score'] = df_processed['anomaly_score'] # Add to original df for tracking

    # Filter for anomalous students from the ORIGINAL dataframe
    anomalous_students_df_original = df[df['is_anomaly'] == -1]

    # Calculate medians/stds for interpretation (using PROCESSED numerical features)
    feature_medians = df_processed[numerical_features_in_df].median()
    feature_stds = df_processed[numerical_features_in_df].std()

    anomalous_students_list = []
    for index, original_row in anomalous_students_df_original.iterrows():
        student_data = original_row.to_dict() # Start with original data for full display
        
        # Identify extreme features for this anomalous student using PROCESSED values
        extreme_features = {}
        
        for feature in numerical_features_in_df:
            # Get the processed value for deviation calculation
            feature_value_processed = df_processed.loc[index, feature]
            
            # Check for NaN and ensure it's numeric before comparison
            if pd.notna(feature_value_processed) and pd.api.types.is_numeric_dtype(feature_value_processed):
                median_val = feature_medians.get(feature, np.nan) 
                std_val = feature_stds.get(feature, np.nan) 
                
                if pd.notna(median_val) and pd.notna(std_val) and std_val > 0:
                    deviation = (feature_value_processed - median_val) / std_val
                    
                    if abs(deviation) > 1.5: # Threshold for "extreme" deviation
                        extreme_features[feature] = {
                            'value': round(feature_value_processed, 2), # Display the processed value
                            'deviation': round(deviation, 2),
                            'median': round(median_val, 2),
                            'description': ""
                        }
                        if deviation > 0:
                            extreme_features[feature]['description'] = "higher than average"
                        else:
                            extreme_features[feature]['description'] = "lower than average"
        
        student_data['anomaly_score'] = f"{original_row.get('anomaly_score', 0):.4f}"
        student_data['extreme_features'] = extreme_features
        
        student_data['student_id'] = student_data.get('student_id', f"Unknown_ID_{index}")

        anomalous_students_list.append(student_data)

    return df_processed, anomalous_students_list