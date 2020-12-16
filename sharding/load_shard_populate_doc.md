# Load, shard, and populate collections according to task requirements

This document assumes the docker containers are set up according to 00-setup-sharding-doc.md.

## Import json data files to collections with mongoimport

First, we need to copy the data files into the docker container hosting the mongos router. Here, the name of the mongos container is 'mongos'.
```
docker cp proj_data/user.dat mongos:/user.dat
docker cp proj_data/article.dat mongos:/article.dat
docker cp proj_data/read.dat mongos:/read.dat
```

Then, we enter the mongos container's bash shell. 
```
docker exec -it mongos bash
```

Inside the bash shell, we mongoimport the json files stored there into our database 'ddbs'.
```
mongoimport --db ddbs --collection user --file user.dat
mongoimport --db ddbs --collection article --file article.dat
mongoimport --db ddbs --collection read --file read.dat
```

To check if the collections are loaded, enter the mongo shell in the mongos bash shell.
```
mongos
```
Inside the mongo shell, try commands below to check out the collections.
```
mongos> show dbs
mongos> use ddbs
mongos> show collections
mongos> db.user.findOne()
```

## Implement sharding and zoning for user and article collections

We need to shard db.user according to "region", with "Beijing" in dbms1shard, and "Hong Kong" in dbms2shard. For db.article, we need to shard according to "category", with "science" in dbms1shard and dbms2shard, and "technology" in dbms2shard. 

Note that everything to do with collection manipulation happens inside the mongo shell of the mongos container.


### Sharding for db.user

Refer to [MongoDB Official documentation for sharding and zoning by location for more details](https://docs.mongodb.com/manual/tutorial/sharding-segmenting-data-by-location/)

First, we need to enable sharding on the ddbs database.
```
mongos> use ddbs
mongos> sh.enableSharding("ddbs")
```
Before enabling sharding on the db.user collection, we first set the index on the db.user collection which would be the key for sharding. The choice of index is important, and here we choose a compound index composed of "region" and "uid" - region because we need to shard by region, and uid to provide high cardinality for more evenly distributed sharding. The '1' value for the index fields refer to range-based sharding (as opposed to hash-based sharding), which means that the index values close together will be put in the same shard.
```
mongos> db.user.createIndex({"region": 1, "uid": 1})
mongos> sh.shardCollection("ddbs.user", {"region": 1, "uid": 1})
```

As a good practice, we first disable balancing on db.user so that as we configure the sharding, no migration of documents occur, until we enable it.
```
mongos> sh.disableBalancing("ddbs.user")
```

Then, we configure sharding zones to set a region tag for each dbms shard. The MinKey and MaxKey are reserved special values that represent the min and max range of the index values.
```
mongos> sh.addShardTag("dbms1rs", "BJ")
mongos> sh.addTagRange(
            "ddbs.user",
            {"region": "Beijing", "uid": MinKey},
            {"region": "Beijing", "uid": MaxKey},
            "BJ"
        )
mongos> sh.addShardTag("dbms2rs", "HK")
mongos> sh.addTagRange(
            "ddbs.user",
            {"region": "Hong Kong", "uid": MinKey},
            {"region": "Hong Kong", "uid": MaxKey},
            "HK"
        )
```
Now, we are done with configuring the shard zones and can enable balancing so that the documents can migrate to the correct shards. This might take a while (a few minutes for collection of 10000 documents). After waiting for a while, we can check the shard status and distribution.
```
mongos> sh.enableBalancing("ddbs.user")
mongos> sh.status()
mongos> db.user.getShardDistribution()
```

### Sharding for db.article

Now we do the same for db.article. The difficulty is that the task requires us to have "science" articles in both dbms1shard and dbms2shard. However, sharding only does not allow duplication across different shards since mongodb replication sets already account for replication. Therefore, we first do normal sharding to allocate "science" articles to dbms1shard, and "technology" articles to dbms2shardd. Then, we create another collection db.articlesci and allocate it to dbms2shard, and also dynamically update db.articlesci when db.article is updated.

#### Standard sharding procedure for db.article
"science" articles to dbms1shard, "technology" articles to dbms2shard.
```
mongos> db.article.createIndex({"category": 1, "aid": 1})
mongos> sh.shardCollection("ddbs.article", {"category": 1, "aid": 1})
mongos> sh.disableBalancing("ddbs.article")
mongos> sh.addShardTag("dbms1rs", "SCI")
mongos> sh.addTagRange(
            "ddbs.article",
            {"category": "science", "aid": MinKey},
            {"category": "science", "aid": MaxKey},
            "SCI"
        )
mongos> sh.addShardTag("dbms2rs", "TECH")
mongos> sh.addTagRange(
            "ddbs.article",
            {"category": "technology", "aid": MinKey},
            {"category": "technology", "aid": MaxKey},
            "TECH"
        )
mongos> sh.enableBalancing("ddbs.article")
mongos> sh.status()
mongos> db.article.getShardDistribution()
```

##### Create db.articlesci and assign to dbms2shard
Using mongodb's aggregate pipeline, we extract articles with category: "science" into another collection db.articlesci. 
```
db.article.aggregate([
    { $match: {category: "science"}},
    { $merge: {into: "articlesci", whenMatched: "replace"}}
])
```

Apply sharding to db.articlesci, by assigning all of it to dbms2shard.
```
mongos> db.articlesci.createIndex({"category": 1, "aid": 1})
mongos> sh.shardCollection("ddbs.articlesci", {"category": 1, "aid": 1})
mongos> sh.disableBalancing("ddbs.articlesci")
mongos> sh.addShardTag("dbms2rs", "SCI2")
mongos> sh.addTagRange(
            "ddbs.articlesci",
            {"category": "science", "aid": MinKey},
            {"category": "science", "aid": MaxKey},
            "SCI2"
        )
mongos> sh.enableBalancing("ddbs.articlesci")
mongos> sh.status()
mongos> db.articlesci.getShardDistribution()
```
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

## Implementing sharding for read collection
We have to shard db.read according to user region, so first we need to add a region column to db.read, set that as index, and configure sharding zones based on it.

### Adding region column to db.read
We use aggregate pipeline with $lookup to perform the join, which is not as intuitive in mongodb as in sql. 

We first create another temporary collection db.uid_reg from db.user as $lookup only works on unsharded collections.
```
mongos> db.user.aggregate([
            { $project: {uid:1, region: 1}},
            { $out: "uid_reg"}
        ])
```

Then, we create db.read_reg by joining db.read with db.uid_reg using $lookup.
```
mongos> use ddbs
mongos> db.read.aggregate([
                { $lookup: {from: "uid_reg", localField: "uid", foreignField: "uid", as: "someField"}},
                { $addFields: { region: "$someField.region"}},
                { $unwind: "$region"},
                { $project: { someField: 0}},
                { $out: "read_reg"}
            ])
```
Note that the join takes approximately an hour for 1mil documents in db.read. To observe the progress, open another terminal for mongos bash and inspect the tmp collection which should have a name like "tmp.agg_out..."

### Sharding db.read_reg based on region
This is just the standard sharding procedure like what we did for db.user.
```
mongos> db.read_reg.createIndex({"region": 1, "id": 1})
mongos> sh.shardCollection("ddbs.read_reg", {"region": 1, "id": 1})
mongos> sh.disableBalancing("ddbs.read_reg")
mongos> sh.addShardTag("dbms1rs", "BJ")
mongos> sh.addTagRange(
            "ddbs.read_reg",
            {"region": "Beijing", "id": MinKey},
            {"region": "Beijing", "id": MaxKey},
            "BJ"
        )
mongos> sh.addShardTag("dbms2rs", "HK")
mongos> sh.addTagRange(
            "ddbs.read_reg",
            {"region": "Hong Kong", "id": MinKey},
            {"region": "Hong Kong", "id": MaxKey},
            "HK"
        )
mongos> sh.enableBalancing("ddbs.read_reg")
mongos> sh.status()
mongos> db.read_reg.getShardDistribution()
```

## Populate and shard db.beread

To populate db.beread, we need to group db.read by "aid" and do some aggregation: (1) reads: count the total number of reads, form a list of all users who read it, (2) comment: count number of comments, form a list of all users who commented on it, (3) agrees: count number of agrees, form a list of users who agreed with it, (4) shares: count number of shares, form a list of users who shared it. We also need to shard db.beread according to article category, so we should also add a "category" column to db.beread.

### Populate db.beread
First, we form a temporary db.aid_cat_ts as $lookup only works on unsharded collections.
```
mongos> db.article.aggregate([
            { $project: {aid:1, category: 1, timestamp: 1}},
            { $out: "aid_cat"}
        ])
```

Then, we populate db.beread using a rather complex aggregation pipeline.

```
mongos> db.read.aggregate(
            [
                // group by aid and create new fields with aggregated counts and arrays
                {
                    $group: {
                        _id: "$aid",
                        readNum: { $sum: {$toInt: "$readOrNot" } },
                        readUidList: { $addToSet: { $cond: { if: { $eq: ["$readOrNot","1"] }, then: "$uid", else: "$$REMOVE"} } },
                        commentNum: { $sum: {$toInt: "$commentOrNot" } },
                        commentUidList: { $addToSet: { $cond: { if: { $eq: ["$commentOrNot","1"] }, then: "$uid", else: "$$REMOVE"} } },
                        agreeNum: { $sum: {$toInt: "$agreeOrNot" } },
                        agreeUidList: { $addToSet: { $cond: { if: { $eq: ["$agreeOrNot","1"] }, then: "$uid", else: "$$REMOVE"} } },
                        shareNum: { $sum: {$toInt: "$shareOrNot" } },
                        shareUidList: { $addToSet: { $cond: { if: { $eq: ["$shareOrNot","1"] }, then: "$uid", else: "$$REMOVE"} } },
                    }
                },

                // Modify aid from integer to string
                { $addFields: { "aid": {$concat: [ "a", "$_id" ]}}},

                // Join with article category
                { $lookup: { from: "aid_cat", localField: "_id", foreignField: "aid", as: "someField"}},
                { $addFields: { category: "$someField.category", timestamp: "$someField.timestamp"}},
                { $unwind: "$category", "$timestamp"},
                { $project: {someField: 0}},
                { $out: "beread"}
            ]
        )
```
This step is quite fast, about a few minutes, since there's only 10000 articles.

### Sharding db.beread
Then, we do the same sharding process as db.article: "science" articles to dbms1shard, "technology" articles to dbms2shard.
```
mongos> db.beread.createIndex({"category": 1, "aid": 1})
mongos> sh.shardCollection("ddbs.beread", {"category": 1, "aid": 1})
mongos> sh.disableBalancing("ddbs.beread")
mongos> sh.addShardTag("dbms1rs", "SCI")
mongos> sh.addTagRange(
            "ddbs.beread",
            {"category": "science", "aid": MinKey},
            {"category": "science", "aid": MaxKey},
            "SCI"
        )
mongos> sh.addShardTag("dbms2rs", "TECH")
mongos> sh.addTagRange(
            "ddbs.beread",
            {"category": "technology", "aid": MinKey},
            {"category": "technology", "aid": MaxKey},
            "TECH"
        )
mongos> sh.enableBalancing("ddbs.beread")
mongos> sh.status()
mongos> db.beread.getShardDistribution()
```
Create db.bereadsci and assign to dbms2shard.
```
db.beread.aggregate([
    { $match: {category: "science"}},
    { $merge: {into: "bereadsci", whenMatched: "replace"}}
])
```

Apply sharding to db.bereadsci, by assigning all of it to dbms2shard.
```
mongos> db.bereadsci.createIndex({"category": 1, "aid": 1})
mongos> sh.shardCollection("ddbs.bereadsci", {"category": 1, "aid": 1})
mongos> sh.disableBalancing("ddbs.bereadsci")
mongos> sh.addShardTag("dbms2rs", "SCI2")
mongos> sh.addTagRange(
            "ddbs.bereadsci",
            {"category": "science", "aid": MinKey},
            {"category": "science", "aid": MaxKey},
            "SCI2"
        )
mongos> sh.enableBalancing("ddbs.bereadsci")
mongos> sh.status()
mongos> db.bereadsci.getShardDistribution()
```
#### Auto refresh of db.bereadsci
Edit the auto_refresh.py script to update db.bereadsci when db.read updated

## Populating and sharding db.poprank
We populate db.poprank by aggregating db.read. First, we group the timestamps by month, and within each month group, we group documents by aid, and then finally aggregate as in db.beread to get the new field readNum per article per month. Then within each month, we sort the articles by their readNum in descending order. We then create another field articleAidList that stores the first five articles in each month in an array. 
We repeat again for weekly and daily groups.

```
mongos> db.read.aggregate(
            [
                // group by aid and create new fields with aggregated counts and arrays
                {
                    $group: {
                        _id: "$aid",
                        readNum: { $sum: {$toInt: "$readOrNot" } },
                        readUidList: { $addToSet: { $cond: { if: { $eq: ["$readOrNot","1"] }, then: "$uid", else: "$$REMOVE"} } },
                        commentNum: { $sum: {$toInt: "$commentOrNot" } },
                        commentUidList: { $addToSet: { $cond: { if: { $eq: ["$commentOrNot","1"] }, then: "$uid", else: "$$REMOVE"} } },
                        agreeNum: { $sum: {$toInt: "$agreeOrNot" } },
                        agreeUidList: { $addToSet: { $cond: { if: { $eq: ["$agreeOrNot","1"] }, then: "$uid", else: "$$REMOVE"} } },
                        shareNum: { $sum: {$toInt: "$shareOrNot" } },
                        shareUidList: { $addToSet: { $cond: { if: { $eq: ["$shareOrNot","1"] }, then: "$uid", else: "$$REMOVE"} } },
                    }
                },

                // Modify aid from integer to string
                { $addFields: { "aid": {$concat: [ "a", "$_id" ]}}},

                // Join with article category
                { $lookup: { from: "aid_cat", localField: "_id", foreignField: "aid", as: "someField"}},
                { $addFields: { category: "$someField.category"}},
                { $unwind: "$category"},
                { $project: {someField: 0}},
                { $out: "beread"}
            ]
        )
```