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


class Mongo:
    def __init__(self):
        self.client = None
        self.db = None

    def init_app(self, app):
        uri = app.config.get("MONGO_URI", "mongodb://localhost:27017/")
        db_name = app.config.get("DB_NAME", "defaul_name_from_db_helper")
        
        self.client = MongoClient(uri)
        self.db = self.client[db_name]

        app.db = self.db
