import pymongo
from pymongo import MongoClient
import time

client = MongoClient('mongodb://192.168.1.152:60000/')
db = client.ddbs_proj

with db.article.watch(
        [{'$match': {'fullDocument.category': 'science'}}]) as stream:
    for change in stream:
        print(change)
        db.article.aggregate([
            {"$match": {"category": "science"}},
            {"$merge": {"into": "articlesci", "whenMatched":"replace"}}
        ])