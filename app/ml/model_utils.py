import joblib
import os
import pandas as pd

MODEL_DIR = os.path.join(os.getcwd(), "app", "ml", "models")
os.makedirs(MODEL_DIR, exist_ok=True)

def load_latest_dataset():
    import os
    folder = 'uploads'
    files = sorted(
        [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(('csv', 'json'))],
        key=os.path.getmtime,
        reverse=True
    )
    if not files:
        raise FileNotFoundError("No data files found in uploads folder")

    latest = files[0]
    if latest.endswith('.csv'):
        return pd.read_csv(latest)
    return pd.read_json(latest)

def save_model(model, name):
    path = os.path.join(MODEL_DIR, f"{name}.pkl")
    joblib.dump(model, path)

def load_model(name):
    path = os.path.join(MODEL_DIR, f"{name}.pkl")
    return joblib.load(path)
