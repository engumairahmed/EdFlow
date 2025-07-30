# app/utils/db.py

from pymongo import MongoClient
from config import Config

import logging

logger = logging.getLogger(__name__)

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

        if not uri:
            logger.error("MONGO_URI is not set in Flask app configuration.")
            raise ValueError("MONGO_URI must be set in Flask app config.")
        if not db_name:
            logger.error("DB_NAME is not set in Flask app configuration.")
            raise ValueError("DB_NAME must be set in Flask app config.")
        
        try:
            self.client = MongoClient(uri)
            self.db = self.client[db_name]
            
            self.client.admin.command('ping')
            logger.info(f"Successfully connected to MongoDB at {uri}, database: {db_name}")

            app.mongo_client = self.client
            app.db = self.db

        except Exception as e:
            logger.critical(f"Failed to connect to MongoDB at {uri}: {e}")
            raise ConnectionError(f"Could not connect to MongoDB: {e}")
