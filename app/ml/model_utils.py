from flask import current_app
from datetime import datetime, timezone
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
            'trained_at': datetime.now(timezone.utc),
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

def get_classification_models_summary():
    """
    Retrieves a summary of the first three classification models from the
    latest trained model document, with a combined and formatted model name.
    """
    db = current_app.db
    models_summary = []

    try:
        # Find the latest document (most recent training run)
        latest_model_group = db.trained_models.find_one(
            {},
            sort=[('created_at', -1)]
        )

        if latest_model_group and 'details' in latest_model_group:
            dataset_name = latest_model_group.get('dataset', 'Unknown Dataset')
            
            for detail in latest_model_group['details']:
                if detail.get('type') == 'classification':
                    
                    # Get the raw model names
                    model_type = detail.get('type', 'Unknown Type').title() # Capitalize the type
                    model_name_raw = detail.get('model_name', 'Unknown Model')

                    # Format the model name
                    formatted_model_name = model_name_raw.replace('_', ' ').title()
                    
                    # Create the combined name string using the formatted names
                    combined_name = f"{dataset_name} | {model_type} | {formatted_model_name}"
                    
                    models_summary.append({
                        'id': str(latest_model_group.get('_id')),
                        'dataset': dataset_name,
                        'model_name': formatted_model_name, # Use the formatted name here
                        'combined_name': combined_name,
                        'model_type': model_type,
                        'metrics': detail.get('metrics', {}),
                        'model_path': detail.get('model_path'),
                        'trained_at': latest_model_group.get('created_at', datetime.min.replace(tzinfo=timezone.utc))
                    })

    except Exception as e:
        current_app.logger.error(f"Error retrieving trained models summary: {e}", exc_info=True)

    return models_summary