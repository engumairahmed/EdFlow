import os
import pandas as pd
import joblib
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from pymongo import MongoClient
from datetime import datetime
import numpy as np

from app import mongo

# MongoDB setup
db = mongo.db
metrics_collection = db['model_metrics']
runs_collection = db['trained_models']
datasets_collection = db['uploaded_datasets']  # NEW: collection for uploaded dataset

# Folder to store models
MODEL_DIR = 'app/ml/models'

# Columns to exclude
EXCLUDED_COLUMNS = ['student_id', 'gender']

def try_convert_float(value):
    try:
        return float(value)
    except:
        return np.nan

def train_models_and_save_metrics(df: pd.DataFrame, dataset_name: str):
    dataset_dir = os.path.join(MODEL_DIR, dataset_name).replace("\\", "/")
    lr_dir = os.path.join(dataset_dir, 'lr').replace("\\", "/")
    rf_dir = os.path.join(dataset_dir, 'rf').replace("\\", "/")

    # Create required folders
    os.makedirs(lr_dir, exist_ok=True)
    os.makedirs(rf_dir, exist_ok=True)

    # Convert values to float where possible
    df_cleaned = df.copy()
    for col in df_cleaned.columns:
        if col not in EXCLUDED_COLUMNS:
            df_cleaned[col] = df_cleaned[col].apply(try_convert_float)

    target_columns = [col for col in df_cleaned.columns if col not in EXCLUDED_COLUMNS]

    last_run_results = []

    for target in target_columns:
        try:
            data = df_cleaned.dropna(subset=[target])
            if len(data) < 10:
                print(f"⏭️ Skipping {target}: not enough data")
                continue

            X = data.drop(columns=[target] + EXCLUDED_COLUMNS)
            y = data[target]

            if X.select_dtypes(include=[float, int]).shape[1] == 0:
                print(f"⏭️ Skipping {target}: no valid numeric features")
                continue

            # Fill missing values
            X = X.fillna(0)

            metrics = {
                'dataset': dataset_name,
                'target': target,
                'timestamp': datetime.now()
            }

            # Linear Regression
            try:
                lr = LinearRegression()
                lr.fit(X, y)
                y_pred_lr = lr.predict(X)
                mse_lr = mean_squared_error(y, y_pred_lr)
                r2_lr = r2_score(y, y_pred_lr)

                lr_path = os.path.join(lr_dir, f'{target}_lr.pkl').replace("\\", "/")
                joblib.dump(lr, lr_path)

                metrics['linear_regression'] = {
                    'mse': mse_lr,
                    'r2_score': r2_lr,
                    'model_path': lr_path
                }
                print(f"✅ Linear Regression saved: {lr_path}")
            except Exception as e:
                print(f"❌ Linear Regression failed for {target}: {e}")

            # Random Forest
            try:
                rf = RandomForestRegressor(n_estimators=100, random_state=42)
                rf.fit(X, y)
                y_pred_rf = rf.predict(X)
                mse_rf = mean_squared_error(y, y_pred_rf)
                r2_rf = r2_score(y, y_pred_rf)

                rf_path = os.path.join(rf_dir, f'{target}_rf.pkl').replace("\\", "/")
                joblib.dump(rf, rf_path)

                metrics['random_forest'] = {
                    'mse': mse_rf,
                    'r2_score': r2_rf,
                    'model_path': rf_path
                }
                print(f"🌲 Random Forest saved: {rf_path}")
            except Exception as e:
                print(f"❌ Random Forest failed for {target}: {e}")

            metrics_collection.insert_one(metrics)
            last_run_results.append(metrics)

        except Exception as e:
            print(f"⚠️ Unexpected error for {target}: {e}")

    # Save full run summary
    runs_collection.insert_one({
        'dataset': dataset_name,
        'timestamp': datetime.now(),
        'total_models': len(last_run_results),
        'details': last_run_results
    })

    print(f"📝 MongoDB record saved for model: {dataset_name}")

    # ✅ Save the raw dataset in MongoDB (max 5000 rows)
    df_sample = df.head(5000)
    dataset_dicts = df_sample.to_dict(orient='records')
    print(dataset_dicts)
    if dataset_dicts:
        datasets_collection.insert_one({
            'dataset_name': dataset_name,
            'uploaded_at': datetime.now(),
            'sample_data': dataset_dicts
        })
        print(f"📦 Dataset saved in MongoDB: {dataset_name}")
    else:
        print(f"⚠️ Dataset was empty or could not be parsed")

