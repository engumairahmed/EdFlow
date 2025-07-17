from flask_pymongo import PyMongo

mongo = PyMongo()

# Utility to access collections
def get_users_collection():
    return mongo.db.users

def get_climate_data_collection():
    return mongo.db.climate_data
