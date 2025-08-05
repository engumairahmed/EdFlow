# app/ml/anomaly_detector.py

import logging
import os
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from app import mongo

# MongoDB database instance
db = mongo.db

# File path for uploaded data (should match your config)
UPLOADS_DIR = os.path.join(os.getcwd(), "uploads")

logger = logging.getLogger(__name__)

def run_isolation_forest(df):
    """
    Runs Isolation Forest on a given DataFrame and returns the results.
    """
    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    categorical_cols = df.select_dtypes(exclude=np.number).columns.tolist()

    df_processed = pd.get_dummies(df, columns=categorical_cols, drop_first=True)
    df_processed = df_processed.fillna(df_processed.median())

    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(df_processed)

    df['is_anomaly'] = model.predict(df_processed)
    df['anomaly_score'] = model.decision_function(df_processed)
    
    return df, df_processed

def get_insights(df_anomalies):
    """
    Generates human-readable insights from the anomalous data.
    """
    anomaly_insights = {}
    if not df_anomalies.empty:
        if 'gender' in df_anomalies.columns:
            gender_counts = df_anomalies['gender'].value_counts()
            if 'Male' in gender_counts and 'Female' in gender_counts:
                if gender_counts['Male'] > gender_counts['Female'] * 1.5:
                    anomaly_insights['gender_insight'] = "Significantly more male students were flagged as anomalous."
                elif gender_counts['Female'] > gender_counts['Male'] * 1.5:
                    anomaly_insights['gender_insight'] = "Significantly more female students were flagged as anomalous."
                else:
                    anomaly_insights['gender_insight'] = "Anomalies are relatively balanced across genders."
        
        if 'anomaly_score' in df_anomalies.columns:
            if len(df_anomalies[df_anomalies['anomaly_score'] < -0.2]) > len(df_anomalies) / 2:
                anomaly_insights['score_insight'] = "Most anomalies have very low scores, indicating strong deviation from the norm."
            else:
                anomaly_insights['score_insight'] = "Anomalies are concentrated around the detection threshold."
    
    return anomaly_insights

def detect_anomalies_from_db():
    """
    Fetches student data from MongoDB, detects anomalies, and returns the results.
    """
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
        logger.error(f"Error connecting to or processing data from MongoDB: {e}")
        return [], {}, 0

def find_extreme_features(row, feature_names, model):
    """
    Finds the most extreme features for a given anomalous data point.
    """
    data_point = row[feature_names].values.reshape(1, -1)
    
    feature_contributions = model.decision_function(data_point)
    
    most_extreme_feature_index = np.argmax(np.abs(feature_contributions))
    
    feature_name = feature_names[most_extreme_feature_index]
    feature_value = row[feature_name]
    
    description = "Unusually low" if feature_contributions[0] < 0 else "Unusually high"
    
    return {
        feature_name: {
            'value': feature_value,
            'description': description
        }
    }

def detect_anomalies_from_df(file_name, n_estimators=100, contamination=0.05, random_state=42):
    file_path = os.path.join(UPLOADS_DIR, file_name)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found at: {file_path}")
    if file_name.endswith('.csv'):
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)
    total_students = len(df)
    
    features_to_use = []
    
    if 'age' in df.columns:
        features_to_use.append('age')
    if 'total_score' in df.columns:
        features_to_use.append('total_score')
    if 'attendance' in df.columns:
        features_to_use.append('attendance')

    if not features_to_use:
        return pd.DataFrame(), {'error': 'No suitable numerical features (age, total_score, attendance) found in the file for anomaly detection.'}, total_students

    if 'gender' in df.columns:
        df['gender'] = df['gender'].astype('category').cat.codes
        features_to_use.append('gender')
    if 'class_label' in df.columns:
        df['class_label'] = df['class_label'].astype('category').cat.codes
        features_to_use.append('class_label')

    X = df[features_to_use]
    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(X)
    df['anomaly_score'] = model.decision_function(X)
    df['is_anomaly'] = model.predict(X)
    anomalous_df = df[df['is_anomaly'] == -1].copy()
    if anomalous_df.empty:
        return pd.DataFrame(), {}, total_students

    anomalous_df['extreme_features'] = anomalous_df.apply(
        lambda row: find_extreme_features(row, X.columns, model), axis=1
    )
    
    insights = get_insights(anomalous_df)
    return anomalous_df, insights, total_students

def detect_student_anomalies(file_name):
    """
    Detects anomalies from a specified file or the MongoDB database using Isolation Forest.
    Returns a dataframe of anomalous students, insights, and total student count.
    """
    df = pd.DataFrame()
    if file_name:
        file_path = os.path.join(UPLOADS_DIR, file_name)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found at: {file_path}")
            
        if file_name.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
    else:
        students_collection = db.students
        all_students_data = list(students_collection.find())
        if not all_students_data:
            return pd.DataFrame(), {}, 0
        df = pd.DataFrame(all_students_data)
        if '_id' in df.columns:
            df.rename(columns={'_id': 'student_id'}, inplace=True)
        
    total_students = len(df)
    
    features_to_use = []
    if 'age' in df.columns:
        features_to_use.append('age')
    if 'total_score' in df.columns:
        features_to_use.append('total_score')
    if 'attendance' in df.columns:
        features_to_use.append('attendance')

    if not features_to_use:
        return pd.DataFrame(), {'error': 'No suitable numerical features found in the dataset.'}, total_students

    if 'gender' in df.columns:
        df['gender'] = df['gender'].astype('category').cat.codes
        features_to_use.append('gender')
    if 'class_label' in df.columns:
        df['class_label'] = df['class_label'].astype('category').cat.codes
        features_to_use.append('class_label')

    X = df[features_to_use]
    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(X)
    
    df['anomaly_score'] = model.decision_function(X)
    df['is_anomaly'] = model.predict(X)
    
    anomalous_df = df[df['is_anomaly'] == -1].copy()
    
    if anomalous_df.empty:
        return pd.DataFrame(), {}, total_students

    anomalous_df['extreme_features'] = anomalous_df.apply(
        lambda row: find_extreme_features(row, X.columns, model), axis=1
    )
    
    insights = get_insights(anomalous_df)
    
    return anomalous_df, insights, total_students