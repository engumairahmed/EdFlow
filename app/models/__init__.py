from app import mongo


# Utility to access collections
def get_users_collection():
    return mongo.db.users

def get_climate_data_collection():
    return mongo.db.climate_data

def get_contact_collection():
    return mongo.db.contacts

def get_feedbacks_collection():
    return mongo.db.feedbacks
