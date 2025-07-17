# app/ml/dataset_manager.py

import os
import pandas as pd
from hashlib import sha256

from app.utils.mongodb_utils import delete_dataset_by_hash, insert_dataset

UPLOADS_DIR = os.path.join(os.getcwd(), "uploads")

def hash_dataframe(df: pd.DataFrame):
    # Basic hash using structure and sample data
    structure_hash = sha256((",".join(df.columns)).encode()).hexdigest()
    return structure_hash

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

        # Create new merged filename
        new_file_index = len(os.listdir(UPLOADS_DIR)) + 1
        new_file_name = f"merged_dataset_{new_file_index}.csv"
        new_file_path = os.path.join(UPLOADS_DIR, new_file_name)

        # Save merged data to new file
        save_dataset(merged_df, new_file_path)

        # Insert merged data to MongoDB
        insert_dataset(merged_df, hash_dataframe(merged_df))

        return f"Dataset matched with {os.path.basename(matched_file)} and saved as new file {new_file_name}."
    
    else:
        # New dataset, just save it
        file_name = f"dataset_{len(os.listdir(UPLOADS_DIR)) + 1}.csv"
        file_path = os.path.join(UPLOADS_DIR, file_name)
        save_dataset(new_df, file_path)

        insert_dataset(new_df, hash_dataframe(new_df))
        return f"New dataset saved as {file_name} and inserted in MongoDB."
