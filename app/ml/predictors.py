import pandas as pd
from sklearn.metrics import r2_score
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from app.ml.model_utils import save_model, load_model
import os
import joblib

MODEL_DIR = os.path.join(os.getcwd(), "app", "ml", "models")

def train_anomaly_model(data: pd.DataFrame):
    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(data)
    save_model(model, "anomaly_detector")

def detect_anomalies(data: pd.DataFrame):
    model = load_model("anomaly_detector")
    data["anomaly"] = model.predict(data)
    return data[data["anomaly"] == -1]

def train_predictor(data: pd.DataFrame, target: str):
    X = data.drop(columns=[target])
    y = data[target]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestRegressor(n_estimators=100)
    model.fit(X_train, y_train)

    # Predict on test set
    y_pred = model.predict(X_test)

    # Compute accuracy (R² score)
    accuracy = r2_score(y_test, y_pred)

    return model, accuracy

def predict(data: pd.DataFrame ,model:str):
    model = load_model(model)
    return model.predict(data)

def predict_missing_fields(input_data, model_name):
    df = pd.DataFrame([input_data])
    for column, value in input_data.items():
        if value is None:
            path = os.path.join(MODEL_DIR, model_name, f"{column}.pkl")
            model = joblib.load(path)
            prediction = model.predict(df.drop(columns=[column]))[0]
            df.at[0, column] = prediction
    return df.to_dict(orient="records")[0]