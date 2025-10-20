import os
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
from typing import Dict
from settings import settings


class MongoService:
    def __init__(self, db_name: str, uri: str | None = None):
        mongo_uri = settings.mongodb_uri 
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]

    def insert_one(self, collection_name: str, data: dict):
        data["created_at"] = datetime.now()
        data["updated_at"] = datetime.now()
        return self.db[collection_name].insert_one(data).inserted_id

    def insert_many(self, collection_name: str, data: list):
        for d in data:
            d["created_at"] = datetime.now()
            d["updated_at"] = datetime.now()
        return self.db[collection_name].insert_many(data).inserted_ids

    def find_one(self, collection_name: str, query: dict):
        return self.db[collection_name].find_one(query, {'_id': 0})
        # return self.db[collection_name].find_one(query)

    # def find_many(self, collection_name: str, query: dict = {}, skip: int = 0, limit: int = 10):
    #     cursor = self.db[collection_name].find(query, skip=skip, limit=limit)
    #     return list(cursor)

    def find_many(self, collection_name: str, query: Dict, skip: int = 0, limit: int = 10):
        return list(self.db[collection_name].find(query, {'_id': 0}).skip(skip).limit(limit))

    def count_documents(self, collection_name: str, query: Dict):
        return self.db[collection_name].count_documents(query)

    def update_one(self, collection_name: str, query: dict, data: dict):
        data["updated_at"] = datetime.now()
        return self.db[collection_name].update_one(query, {"$set": data})

    def update_many(self, collection_name: str, queries: list[dict], updates: list[dict]):
        for query, update in zip(queries, updates):
            update["updated_at"] = datetime.now()
            self.db[collection_name].update_one(query, {"$set": update}, upsert=True)

    def delete_one(self, collection_name: str, query: dict):
        return self.db[collection_name].delete_one(query)

    def close(self):
        self.client.close()