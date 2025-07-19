from datetime import datetime
import pandas as pd
from bson.objectid import ObjectId

from app import mongo

# Load from env or use default
# MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
# DB_NAME = os.getenv("DB_NAME", "edflow")  # you can change this as needed

# client = MongoClient(MONGO_URI)
# db = client[DB_NAME]
db = mongo.db
datasets_collection = db["uploaded_datasets"]
model_collection = db["training_runs"]

# === General CRUD Utilities ===

def insert_one(collection_name, data):
    collection = db[collection_name]
    result = collection.insert_one(data)
    return str(result.inserted_id)

def insert_many(collection_name, data_list):
    collection = db[collection_name]
    result = collection.insert_many(data_list)
    return [str(_id) for _id in result.inserted_ids]

def find_one(collection_name, query):
    collection = db[collection_name]
    return collection.find_one(query)

def find_many(collection_name, query={}, projection=None, limit=100):
    collection = db[collection_name]
    return list(collection.find(query, projection).limit(limit))

def update_one(collection_name, query, update_data):
    collection = db[collection_name]
    return collection.update_one(query, {"$set": update_data})

def delete_one(collection_name, query):
    collection = db[collection_name]
    return collection.delete_one(query)

def delete_many(collection_name, query):
    collection = db[collection_name]
    return collection.delete_many(query)

def get_by_id(collection_name, object_id):
    collection = db[collection_name]
    return collection.find_one({"_id": ObjectId(object_id)})

# === Specialized for Dataset Storage ===

def save_dataset_to_mongodb(df, dataset_name, user_id, is_paid):
    try:
        # Convert DataFrame to dictionary
        records = df.to_dict(orient='records')
        doc = {
            "dataset_name": dataset_name,
            "user_id": user_id,
            "is_paid": is_paid,
            "uploaded_at": datetime.now(),
            "record_count": len(records),
            "data": records
        }
        datasets_collection.insert_one(doc)
        print(f"📁 Dataset '{dataset_name}' inserted into MongoDB.")
    except Exception as e:
        print(f"❌ Failed to save dataset to MongoDB: {e}")

def get_dataset_by_model(model_name, limit=5000):
    return find_many("datasets", {"model_name": model_name}, limit=limit)

def insert_dataset(df: pd.DataFrame, hash_val: str):
    data = df.to_dict(orient="records")
    for doc in data:
        doc["hash"] = hash_val
    datasets_collection.insert_many(data)

def delete_dataset_by_hash(hash_val: str):
    datasets_collection.delete_many({"hash": hash_val})