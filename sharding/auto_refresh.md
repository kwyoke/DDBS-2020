Automatically refresh db.articlesci when db.article is updated with "science" articles. This is done in a python script via pymongo and db.collection.watch() which checks for any updates to the collection as the script is running. Simply run the python script auto_refresh.py in the local terminal (doesn't have to be in the container) in the background to ensure that db.articlesci is updated when necessary. $merge is good because it merges changes to existing collection instead of rewriting the entire collection.
```
python -m pip install pymongo
python auto_refresh.py
```

```
#auto_refresh.py
import pymongo
from pymongo import MongoClient

client = MongoClient('mongodb://192.168.1.152:60000/') #connect to host containing mongos router
db = client.ddbs_proj

with db.article.watch(
        [{'$match': {'fullDocument.category': 'science'}}]) as stream:
    for change in stream:
        print(change)
        db.article.aggregate([
            {"$match": {"category": "science"}},
            {"$merge": {"into": "articlesci", "whenMatched":"replace"}}
        ])
```
You can test out the refreshing capability by inserting science articles into db.article. In the mongo shell of mongos container:
```
mongos> use ddbs
mongos> db.article.insert([
            {"aid": "11111", category: "science"},
            {"aid": "22222}
            ])
```
The auto_refresh.py script should print out the changes made, and the db.articlesci should be updated as well.
