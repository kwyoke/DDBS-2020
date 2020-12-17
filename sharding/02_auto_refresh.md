# Setting up auto refreshing of derived collections

For this project, db.user, db.article, and db.read (and db.read_reg_cat) are the raw main collections which will receive insertions, while db.articlesci, db.beread (and db.bereadsci) and db.popRank series are computed from these three main collections. Therefore, we need to be able to automatically refresh the derived collections when there are insertions, updates, and removals from db.user, db.article and db.read. 

Specifically, the refreshes to be performed are summarised as below:

| Collection to watch  | Collection to update | Update to perform |
| ------------- | ------------- | ------------- |
| article  | articlesci  | insert document if category = "science" |
| read  | beread, bereadsci | update fields: {readNum, readUidList, commentNum, commentUidList, agreeNum, agreeUidList, shareNum, shareUidList} for relevant documents with aid matching documents inserted into db.read |
| read | popRank, popRankSci, popRankTech | filter records in db.read with timestamps in the same month as new read, calculate popScoreAgg for each aid within the filtered records for each month/week/day, put top 5 for each month/week/day in arrays, form new documents and insert, replacing if timestamp overlaps |


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
