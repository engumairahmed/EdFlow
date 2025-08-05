from flask import current_app
from datetime import datetime
import logging
from bson.objectid import ObjectId
import joblib
import os
import pandas as pd


logger = logging.getLogger(__name__)

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

def get_model_path(model_name):
    """Generates the full path for a model file."""
    model_dir = MODEL_DIR
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)
        logger.info(f"Created model directory: {model_dir}")
    return os.path.join(model_dir, f"{model_name}.pkl")

def save_model(model, model_name, metrics=None, model_type="Dropout Prediction", trained_by_user_id=None):
    "Saves a model to a file and records its metadata in MongoDB."
    model_path = get_model_path(model_name)
    try:
        joblib.dump(model, model_path)
        logger.info(f"Model '{model_name}' saved to {model_path}")

        # Record model metadata in MongoDB
        db = current_app.db
        model_metadata = {
            'model_name': model_name,
            'model_type': model_type,
            'file_path': model_path,
            'trained_at': datetime.utcnow(),
            'metrics': metrics if metrics is not None else {},
            'trained_by_user_id': ObjectId(trained_by_user_id) if trained_by_user_id else None
        }
        db.trained_models.update_one(
            {'model_name': model_name},
            {'$set': model_metadata},
            upsert=True
        )
        logger.info(f"Metadata for model '{model_name}' saved/updated in MongoDB.")
        return model_path
    except Exception as e:
        logger.error(f"Failed to save model '{model_name}': {e}", exc_info=True)
        return None


def get_trained_models_summary():
    "Retrieves a summary of all trained models from MongoDB."
    db = current_app.db
    models_summary = []
    try:
        for model_doc in db.trained_models.find({}).sort('trained_at', -1):
            models_summary.append({
                'id': str(model_doc.get('_id')),
                'name': model_doc.get('model_name'),
                'type': model_doc.get('model_type'),
                'trained_at': model_doc.get('trained_at', datetime.min),
                'metrics': model_doc.get('metrics', {}),
                'file_path': model_doc.get('file_path'),
                'trained_by_user_id': str(model_doc.get('trained_by_user_id')) if model_doc.get('trained_by_user_id') else 'N/A'
            })
        logger.info(f"Retrieved summary for {len(models_summary)} trained models.")
    except Exception as e:
        logger.info(f"Error retrieving trained models summary: {e}")
        logger.error(f"Error retrieving trained models summary: {e}", exc_info=True)
    return models_summary