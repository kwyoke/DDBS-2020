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
Now, we are done with configuring the shard zones and can enable balancing so that the documents can migrate to the correct shards. This might take a while (a few minutes for collection of 1000 documents). After waiting for a while, we can check the shard status and distribution.
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