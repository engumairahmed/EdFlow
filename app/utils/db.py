# app/utils/db.py

from pymongo import MongoClient
from config import Config

mongo_uri = Config.MONGO_URI
db_name = Config.DB_NAME
_client = MongoClient(mongo_uri) 
def get_mongo_client():
    return _client

def get_database():
    return _client[db_name]