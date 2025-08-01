# app/ml/anomaly_detector.py - Final Code

import pandas as pd
from sklearn.ensemble import IsolationForest
import numpy as np
import os
from app import mongo

# UPLOADS_DIR ko define karenge
UPLOADS_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)), 'uploads')

def run_isolation_forest(df):
    """
    Runs Isolation Forest on a given DataFrame and returns the results.
    """
    # Identify numeric and categorical columns
    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    categorical_cols = df.select_dtypes(exclude=np.number).columns.tolist()

    # Pre-process categorical data using one-hot encoding
    df_processed = pd.get_dummies(df, columns=categorical_cols, drop_first=True)

    # Fill any NaN values that might remain after one-hot encoding
    df_processed = df_processed.fillna(df_processed.median())

    # Initialize and train Isolation Forest model
    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(df_processed)

    # Predict anomalies
    df_processed['is_anomaly'] = model.predict(df_processed)
    df_processed['anomaly_score'] = model.decision_function(df_processed)

    # Map back to original DataFrame
    df['is_anomaly'] = df_processed['is_anomaly']
    df['anomaly_score'] = df_processed['anomaly_score']
    
    return df, df_processed

def get_insights(df_anomalies):
    """
    Generates human-readable insights from the anomalous data.
    """
    anomaly_insights = {}
    if not df_anomalies.empty:
        gender_counts = df_anomalies.get('gender', pd.Series()).value_counts()
        if 'Male' in gender_counts and 'Female' in gender_counts:
            if gender_counts['Male'] > gender_counts['Female'] * 1.5:
                anomaly_insights['gender_insight'] = "Significantly more male students were flagged as anomalous."
            elif gender_counts['Female'] > gender_counts['Male'] * 1.5:
                anomaly_insights['gender_insight'] = "Significantly more female students were flagged as anomalous."
            else:
                anomaly_insights['gender_insight'] = "Anomalies are relatively balanced across genders."
        
        if len(df_anomalies[df_anomalies['anomaly_score'] < -0.2]) > len(df_anomalies) / 2:
            anomaly_insights['score_insight'] = "Most anomalies have very low scores, indicating strong deviation from the norm."
        else:
            anomaly_insights['score_insight'] = "Anomalies are concentrated around the detection threshold."
    
    return anomaly_insights

def detect_anomalies_from_db():
    """
    Fetches student data from MongoDB, detects anomalies, and returns the results.
    """
    db = mongo.db
    students_collection = db.students
    
    try:
        data = list(students_collection.find())
        if not data:
            return [], {}, 0
        
        df = pd.DataFrame(data)
        
        if '_id' in df.columns:
            df = df.drop(columns=['_id'])

        if 'student_name' not in df.columns:
            df['student_name'] = df.get('name', 'N/A')
        if 'studentID' not in df.columns:
            df['studentID'] = df.get('student_id', 'N/A')
        
        df_anomalies, _ = run_isolation_forest(df)

        anomalous_df = df_anomalies[df_anomalies['is_anomaly'] == -1].copy()

        anomaly_insights = get_insights(anomalous_df)
        
        anomalous_students = anomalous_df.to_dict('records')

        return anomalous_students, anomaly_insights, len(df)
        
    except Exception as e:
        print(f"Error connecting to or processing data from MongoDB: {e}")
        return [], {}, 0

def detect_anomalies_from_df(file_name, n_estimators=100, contamination=0.05, random_state=42):
    """
    Detects anomalies in a given pandas DataFrame (from a file) and returns the results.
    """
    DATA_FILE_PATH = os.path.join(UPLOADS_DIR, file_name)

    if not os.path.exists(DATA_FILE_PATH):
        print(f"Error: Data file not found at {DATA_FILE_PATH}.")
        return pd.DataFrame(), {}, 0
    
    try:
        if file_name.endswith('.csv'):
            df = pd.read_csv(DATA_FILE_PATH)
        elif file_name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(DATA_FILE_PATH)
        else:
            raise ValueError("Unsupported file format.")
    except Exception as e:
        print(f"Error reading file at {DATA_FILE_PATH}: {e}")
        return pd.DataFrame(), {}, 0
    
    # Ensure necessary columns are present or handle their absence gracefully
    required_cols = ['student_name', 'studentID']
    for col in required_cols:
        if col not in df.columns:
            df[col] = 'N/A'

    df_anomalies, df_processed = run_isolation_forest(df)

    anomalous_df = df_anomalies[df_anomalies['is_anomaly'] == -1].copy()
    
    anomalous_students_list = []
    if not anomalous_df.empty:
        feature_medians = df_processed.median()
        feature_stds = df_processed.std()

        for _, row in anomalous_df.iterrows():
            student_data = row.to_dict()
            student_data['anomaly_score'] = f"{row.get('anomaly_score', 0):.4f}"

            processed_row = pd.get_dummies(pd.DataFrame([row]), columns=df.select_dtypes(exclude=np.number).columns.tolist(), drop_first=True).iloc[0]
            
            extreme_features = {}
            for feature in processed_row.index:
                feature_value_processed = processed_row[feature]
                median_val = feature_medians.get(feature, np.nan)
                std_val = feature_stds.get(feature, np.nan)

                if pd.notna(median_val) and pd.notna(std_val) and std_val > 0:
                    deviation = (feature_value_processed - median_val) / std_val
                    if abs(deviation) > 1.5:
                        description = "higher than average" if deviation > 0 else "lower than average"
                        original_feature_name = feature.split('_')[0] if '_' in feature else feature
                        original_value = student_data.get(original_feature_name)
                        extreme_features[original_feature_name] = {
                            'value': original_value,
                            'description': description
                        }
            student_data['extreme_features'] = extreme_features
            anomalous_students_list.append(student_data)

    anomaly_insights = get_insights(anomalous_df)
    
    return pd.DataFrame(anomalous_students_list), anomaly_insights, len(df)