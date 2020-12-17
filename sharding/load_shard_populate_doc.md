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
            { $out: "aid_cat_ts"}
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
                { $lookup: { from: "aid_cat_ts", localField: "_id", foreignField: "aid", as: "someField"}},
                { $addFields: { category: "$someField.category", timestamp: "$someField.timestamp"}},
                { $unwind: "$category"},
                { $unwind: "$timestamp"},
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
mongos> db.beread.aggregate([
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

## Populating and sharding popular rank collections

We populate db.poprank by aggregating db.read. We create three separate collections calculating db.poprRankMth, db.popRankWk, db.popRankDay by grouping according to timestamps. Then we combine all three collections into one to form db.popRank. Popularity is calculated by summing up the total number of reads, comments, agrees and shares per article per unit time. 

The task also requires us to generate three types of db.poprank tables: (1) db.popRank contains the ranks of both science and technology articles to be assigned to dbms2shard; (2) db.popRankSci contains the ranks of science articles only and should be assigned to both dbms1shard and dbms2shard; (3) db.popRankTech contains the ranks of technology articles only and should be assigned to dbms2shard.


### Create db.popRank

#### Create db.popRankMth.

Each aggregation pipeline takes about an hour to process given the huge number of records in db.read.
```
mongos> db.read.aggregate([
            // project relevant fields from db.read
            { $project: { date: {"$toDate": {"$toLong": "$timestamp"}}, aid: 1, readOrNot: 1, agreeOrNot: 1, commentOrNot: 1, shareOrNot: 1} },

            // add year and month fields
            { $addFields: {
                year: { $year: "$date"}, 
                month : {$month: "$date"},
                popScore: {$sum: [{$toInt: "$readOrNot"}, {$toInt: "$agreeOrNot"}, {$toInt: "$commentOrNot"}, {$toInt: "$shareOrNot"}]}
            },

            // add unix timestamp defined only by yr and mth
            { $addFields: { timestamp: { $subtract: [ { $dateFromParts: { 'year' : "$year", 'month' : "$month"} }, new Date("1970-01-01") ] }}},

            // Group by year, month, aid and compute popularity score
            {
                $group: {
                    _id: { "timestamp": "$timestamp", "aid": "$aid"},
                    popScoreAgg: { $sum: "$popScore" }
                }
            },

            // sort by popScore each month
            { $sort: {"_id.timestamp": 1, "popScoreAgg": -1} },

            // store all articles in sorted order in array for each month
            {
                $group: {
                    _id: "$_id.timestamp",
                    articleAidList: {$push: "$_id.aid"}
                }
            },

            // keep only top five articles in array
            { 
                $project: { 
                    _id: {$concat: ["m","$_id"]}, 
                    timestamp: "$_id", 
                    articleAidList: { $slice: ["$articleAidList", 5]},
                    temporalGranularity: "monthly"
                    }
            },

            // output
            {"$out": "popRankMth"}
        ]{ allowDiskUse: true })
```

#### Create db.popRankWk.
```
mongos> db.read.aggregate([
            // project relevant fields from db.read
            { $project: { date: {"$toDate": {"$toLong": "$timestamp"}}, aid: 1, readOrNot: 1, agreeOrNot: 1, commentOrNot: 1, shareOrNot: 1} },

            // add year and month fields
            { $addFields: {
                year: { $year: "$date"}, 
                month : {$month: "$date"},
                week: {$week: "$date"},
                popScore: {$sum: [{$toInt: "$readOrNot"}, {$toInt: "$agreeOrNot"}, {$toInt: "$commentOrNot"}, {$toInt: "$shareOrNot"}]}
            },

            // add unix timestamp defined only by yr and mth
            { $addFields: { timestamp: { $subtract: [ { $dateFromParts: { 'isoWeekYear' : "$year", 'isoWeek' : "$week"} }, new Date("1970-01-01") ] }}},

            // Group by year, month, aid and compute popularity score
            {
                $group: {
                    _id: { "timestamp": "$timestamp", "aid": "$aid"},
                    popScoreAgg: { $sum: "$popScore" }
                }
            },

            // sort by popScore each month
            { $sort: {"_id.timestamp": 1, "popScoreAgg": -1} },

            // store all articles in sorted order in array for each month
            {
                $group: {
                    _id: "$_id.timestamp",
                    articleAidList: {$push: "$_id.aid"}
                }
            },

            // keep only top five articles in array
            { 
                $project: { 
                    _id: {$concat: ["w","$_id"]}, 
                    timestamp: "$_id", 
                    articleAidList: { $slice: ["$articleAidList", 5]},
                    temporalGranularity: "weekly"
                    }
            },

            // output
            {"$out": "popRankWk"}
        ]{ allowDiskUse: true })
```


#### Create db.popRankDay.
```
db.read.aggregate([
            // project relevant fields from db.read
            { $project: { date: {"$toDate": {"$toLong": "$timestamp"}}, aid: 1, readOrNot: 1, agreeOrNot: 1, commentOrNot: 1, shareOrNot: 1} },

            // add year and month fields
            { $addFields: {
                year: { $year: "$date"}, 
                month : {$month: "$date"},
                day: {$dayOfYear: "$date"},
                popScore: {$sum: [{$toInt: "$readOrNot"}, {$toInt: "$agreeOrNot"}, {$toInt: "$commentOrNot"}, {$toInt: "$shareOrNot"}]}
            },

            // add unix timestamp defined only by yr and mth
            { $addFields: { timestamp: { $subtract: [ { $dateFromParts: { 'year' : "$year", 'month' : "$month", 'day': "$day" } }, new Date("1970-01-01") ] }}},

            // Group by year, month, aid and compute popularity score
            {
                $group: {
                    _id: { "timestamp": "$timestamp", "aid": "$aid"},
                    popScoreAgg: { $sum: "$popScore" }
                }
            },

            // sort by popScore each month
            { $sort: {"_id.timestamp": 1, "popScoreAgg": -1} },

            // store all articles in sorted order in array for each month
            {
                $group: {
                    _id: "$_id.timestamp",
                    articleAidList: {$push: "$_id.aid"}
                }
            },

            // keep only top five articles in array
            { 
                $project: { 
                    _id: {$concat: ["d","$_id"]}, 
                    timestamp: "$_id", 
                    articleAidList: { $slice: ["$articleAidList", 5]},
                    temporalGranularity: "daily"
                    }
            },

            // output
            {"$out": "popRankDay"}
        ], { allowDiskUse: true })
```
I ran out of RAM when computing db.popRankDay without allowing disk use, so remember to include allowDiskUse: true to offload some of the memory requirements to the disk.

#### Combine db.popRankMth, db.popRankWk, db.popRankDay into one table

First, insert the documents from each collection into db.popRank, then sort each document by timestamp for good measure.
```
mongos> db.popRankMth.find().forEach( function(doc) { db.popRank.insert(doc) })
mongos> db.popRankWk.find().forEach( function(doc) { db.popRank.insert(doc) })
mongos> db.popRankDay.find().forEach( function(doc) { db.popRank.insert(doc) })
mongos> db.popRank.aggregate([ {$sort: {timestamp:1}}, {$out: "popRank"} ])
```

### Create db.popRankSci
First, we need to add "category" field to db.read table so we can filter out science and technology articles. This is similar to what we did for adding the "region" field from db.user. We use back the temporary collection db.aid_cat_ts that is an unsharded collection mapping aid to category.

```
mongos> db.read.aggregate([
                { $lookup: {from: "aid_cat_ts", localField: "aid", foreignField: "aid", as: "someField"}},
                { $addFields: { category: "$someField.category"}},
                { $unwind: "$category"},
                { $project: { someField: 0}},
                { $out: "read_cat"}
            ]{ allowDiskUse: true })
```
Again, this will take about an hour for one million documents in db.read.

Then, we do the same as before, and generate three separate collections, retaining only science articles, and combine the collections into one table.

Monthly:

```
db.read_cat.aggregate([
            // retain only science articles
            { $match: {category: "science"}},

            // project relevant fields from db.read
            { $project: { date: {"$toDate": {"$toLong": "$timestamp"}}, aid: 1, readOrNot: 1, agreeOrNot: 1, commentOrNot: 1, shareOrNot: 1} },

            // add year and month fields
            { $addFields: {
                year: { $year: "$date"}, 
                month : {$month: "$date"},
                popScore: {$sum: [{$toInt: "$readOrNot"}, {$toInt: "$agreeOrNot"}, {$toInt: "$commentOrNot"}, {$toInt: "$shareOrNot"}]}
            },

            // add unix timestamp defined only by yr and mth
            { $addFields: { timestamp: { $subtract: [ { $dateFromParts: { 'year' : "$year", 'month' : "$month"} }, new Date("1970-01-01") ] }}},

            // Group by year, month, aid and compute popularity score
            {
                $group: {
                    _id: { "timestamp": "$timestamp", "aid": "$aid"},
                    popScoreAgg: { $sum: "$popScore" }
                }
            },

            // sort by popScore each month
            { $sort: {"_id.timestamp": 1, "popScoreAgg": -1} },

            // store all articles in sorted order in array for each month
            {
                $group: {
                    _id: "$_id.timestamp",
                    articleAidList: {$push: "$_id.aid"}
                }
            },

            // keep only top five articles in array
            { 
                $project: { 
                    _id: {$concat: ["m","$_id"]}, 
                    timestamp: "$_id", 
                    articleAidList: { $slice: ["$articleAidList", 5]},
                    temporalGranularity: "monthly"
                    }
            },

            // output
            {"$out": "popRankSciMth"}
        ]{ allowDiskUse: true })
```
Weekly:
```
db.read.aggregate([
            // only look for science articles
            { $match: { category: "science"}},

            // project relevant fields from db.read
            { $project: { date: {"$toDate": {"$toLong": "$timestamp"}}, aid: 1, readOrNot: 1, agreeOrNot: 1, commentOrNot: 1, shareOrNot: 1} },

            // add year and month fields
            { $addFields: {
                year: { $year: "$date"}, 
                month : {$month: "$date"},
                week: {$week: "$date"},
                popScore: {$sum: [{$toInt: "$readOrNot"}, {$toInt: "$agreeOrNot"}, {$toInt: "$commentOrNot"}, {$toInt: "$shareOrNot"}]}
            },

            // add unix timestamp defined only by yr and mth
            { $addFields: { timestamp: { $subtract: [ { $dateFromParts: { 'isoWeekYear' : "$year", 'isoWeek' : "$week"} }, new Date("1970-01-01") ] }}},

            // Group by year, month, aid and compute popularity score
            {
                $group: {
                    _id: { "timestamp": "$timestamp", "aid": "$aid"},
                    popScoreAgg: { $sum: "$popScore" }
                }
            },

            // sort by popScore each month
            { $sort: {"_id.timestamp": 1, "popScoreAgg": -1} },

            // store all articles in sorted order in array for each month
            {
                $group: {
                    _id: "$_id.timestamp",
                    articleAidList: {$push: "$_id.aid"}
                }
            },

            // keep only top five articles in array
            { 
                $project: { 
                    _id: {$concat: ["w","$_id"]}, 
                    timestamp: "$_id", 
                    articleAidList: { $slice: ["$articleAidList", 5]},
                    temporalGranularity: "weekly"
                    }
            },

            // output
            {"$out": "popRankSciWk"}
        ]{ allowDiskUse: true })
```
Daily:
```
db.read_cat.aggregate([
            // only look for science articles
            { $match: { category: "science"}},

            // project relevant fields from db.read
            { $project: { date: {"$toDate": {"$toLong": "$timestamp"}}, aid: 1, readOrNot: 1, agreeOrNot: 1, commentOrNot: 1, shareOrNot: 1} },

            // add year and month fields
            { $addFields: {
                year: { $year: "$date"}, 
                month : {$month: "$date"},
                day: {$dayOfYear: "$date"},
                popScore: {$sum: [{$toInt: "$readOrNot"}, {$toInt: "$agreeOrNot"}, {$toInt: "$commentOrNot"}, {$toInt: "$shareOrNot"}]}
            },

            // add unix timestamp defined only by yr and mth
            { $addFields: { timestamp: { $subtract: [ { $dateFromParts: { 'year' : "$year", 'month' : "$month", 'day': "$day" } }, new Date("1970-01-01") ] }}},

            // Group by year, month, aid and compute popularity score
            {
                $group: {
                    _id: { "timestamp": "$timestamp", "aid": "$aid"},
                    popScoreAgg: { $sum: "$popScore" }
                }
            },

            // sort by popScore each month
            { $sort: {"_id.timestamp": 1, "popScoreAgg": -1} },

            // store all articles in sorted order in array for each month
            {
                $group: {
                    _id: "$_id.timestamp",
                    articleAidList: {$push: "$_id.aid"}
                }
            },

            // keep only top five articles in array
            { 
                $project: { 
                    _id: {$concat: ["d","$_id"]}, 
                    timestamp: "$_id", 
                    articleAidList: { $slice: ["$articleAidList", 5]},
                    temporalGranularity: "daily"
                    }
            },

            // output
            {"$out": "popRankSciDay"}
        ], { allowDiskUse: true })
```
Combine into db.popRankSci
```
mongos> db.popRankSciMth.find().forEach( function(doc) { db.popRankSci.insert(doc) })
mongos> db.popRankSciWk.find().forEach( function(doc) { db.popRankSci.insert(doc) })
mongos> db.popRankSciDay.find().forEach( function(doc) { db.popRankSci.insert(doc) })
mongos> db.popRankSci.aggregate([ {$sort: {timestamp:1}}, {$out: "popRankSci"} ])
```

### Create db.popRankTech
We do the same as before, and generate three separate collections, retaining only technology articles, and combine the collections into one table.

Monthly:

```
db.read_cat.aggregate([
            // retain only science articles
            { $match: {category: "technology"}},

            // project relevant fields from db.read
            { $project: { date: {"$toDate": {"$toLong": "$timestamp"}}, aid: 1, readOrNot: 1, agreeOrNot: 1, commentOrNot: 1, shareOrNot: 1} },

            // add year and month fields
            { $addFields: {
                year: { $year: "$date"}, 
                month : {$month: "$date"},
                popScore: {$sum: [{$toInt: "$readOrNot"}, {$toInt: "$agreeOrNot"}, {$toInt: "$commentOrNot"}, {$toInt: "$shareOrNot"}]}
            },

            // add unix timestamp defined only by yr and mth
            { $addFields: { timestamp: { $subtract: [ { $dateFromParts: { 'year' : "$year", 'month' : "$month"} }, new Date("1970-01-01") ] }}},

            // Group by year, month, aid and compute popularity score
            {
                $group: {
                    _id: { "timestamp": "$timestamp", "aid": "$aid"},
                    popScoreAgg: { $sum: "$popScore" }
                }
            },

            // sort by popScore each month
            { $sort: {"_id.timestamp": 1, "popScoreAgg": -1} },

            // store all articles in sorted order in array for each month
            {
                $group: {
                    _id: "$_id.timestamp",
                    articleAidList: {$push: "$_id.aid"}
                }
            },

            // keep only top five articles in array
            { 
                $project: { 
                    _id: {$concat: ["m","$_id"]}, 
                    timestamp: "$_id", 
                    articleAidList: { $slice: ["$articleAidList", 5]},
                    temporalGranularity: "monthly"
                    }
            },

            // output
            {"$out": "popRankTechMth"}
        ]{ allowDiskUse: true })
```
Weekly:
```
db.read.aggregate([
            // only look for science articles
            { $match: { category: "technology"}},

            // project relevant fields from db.read
            { $project: { date: {"$toDate": {"$toLong": "$timestamp"}}, aid: 1, readOrNot: 1, agreeOrNot: 1, commentOrNot: 1, shareOrNot: 1} },

            // add year and month fields
            { $addFields: {
                year: { $year: "$date"}, 
                month : {$month: "$date"},
                week: {$week: "$date"},
                popScore: {$sum: [{$toInt: "$readOrNot"}, {$toInt: "$agreeOrNot"}, {$toInt: "$commentOrNot"}, {$toInt: "$shareOrNot"}]}
            },

            // add unix timestamp defined only by yr and mth
            { $addFields: { timestamp: { $subtract: [ { $dateFromParts: { 'isoWeekYear' : "$year", 'isoWeek' : "$week"} }, new Date("1970-01-01") ] }}},

            // Group by year, month, aid and compute popularity score
            {
                $group: {
                    _id: { "timestamp": "$timestamp", "aid": "$aid"},
                    popScoreAgg: { $sum: "$popScore" }
                }
            },

            // sort by popScore each month
            { $sort: {"_id.timestamp": 1, "popScoreAgg": -1} },

            // store all articles in sorted order in array for each month
            {
                $group: {
                    _id: "$_id.timestamp",
                    articleAidList: {$push: "$_id.aid"}
                }
            },

            // keep only top five articles in array
            { 
                $project: { 
                    _id: {$concat: ["w","$_id"]}, 
                    timestamp: "$_id", 
                    articleAidList: { $slice: ["$articleAidList", 5]},
                    temporalGranularity: "weekly"
                    }
            },

            // output
            {"$out": "popRankTech"}
        ]{ allowDiskUse: true })
```
Daily:
```
db.read_cat.aggregate([
            // only look for science articles
            { $match: { category: "technology"}},

            // project relevant fields from db.read
            { $project: { date: {"$toDate": {"$toLong": "$timestamp"}}, aid: 1, readOrNot: 1, agreeOrNot: 1, commentOrNot: 1, shareOrNot: 1} },

            // add year and month fields
            { $addFields: {
                year: { $year: "$date"}, 
                month : {$month: "$date"},
                day: {$dayOfYear: "$date"},
                popScore: {$sum: [{$toInt: "$readOrNot"}, {$toInt: "$agreeOrNot"}, {$toInt: "$commentOrNot"}, {$toInt: "$shareOrNot"}]}
            },

            // add unix timestamp defined only by yr and mth
            { $addFields: { timestamp: { $subtract: [ { $dateFromParts: { 'year' : "$year", 'month' : "$month", 'day': "$day" } }, new Date("1970-01-01") ] }}},

            // Group by year, month, aid and compute popularity score
            {
                $group: {
                    _id: { "timestamp": "$timestamp", "aid": "$aid"},
                    popScoreAgg: { $sum: "$popScore" }
                }
            },

            // sort by popScore each month
            { $sort: {"_id.timestamp": 1, "popScoreAgg": -1} },

            // store all articles in sorted order in array for each month
            {
                $group: {
                    _id: "$_id.timestamp",
                    articleAidList: {$push: "$_id.aid"}
                }
            },

            // keep only top five articles in array
            { 
                $project: { 
                    _id: {$concat: ["d","$_id"]}, 
                    timestamp: "$_id", 
                    articleAidList: { $slice: ["$articleAidList", 5]},
                    temporalGranularity: "daily"
                    }
            },

            // output
            {"$out": "popRankTechDay"}
        ], { allowDiskUse: true })
```
Combine into db.popRankTech
```
mongos> db.popRankTechMth.find().forEach( function(doc) { db.popRankTech.insert(doc) })
mongos> db.popRankTechWk.find().forEach( function(doc) { db.popRankTech.insert(doc) })
mongos> db.popRankTechDay.find().forEach( function(doc) { db.popRankTech.insert(doc) })
mongos> db.popRankTech.aggregate([ {$sort: {timestamp:1}}, {$out: "popRankTech"} ])
```

### Sharding for db.popRank, db.popRankSci, db.popRankTech
We have to shard db.popRank to dbms2shard; db.popRankTech to dbms2shard; db.popRankSci to both dbms1shard and dbms2shard.

#### Sharding db.popRank
All of db.popRank is assigned to dbms2shard.

```
mongos> db.popRank.createIndex({"id": 1})
mongos> sh.shardCollection("ddbs.popRank", {"id": 1})
mongos> sh.disableBalancing("ddbs.popRank")
mongos> sh.addShardTag("dbms2rs", "POPALL")
mongos> sh.addTagRange(
            "ddbs.popRank",
            {"id": MinKey},
            {"id": MaxKey},
            "POPALL"
        )
mongos> sh.enableBalancing("ddbs.popRank")
mongos> sh.status()
mongos> db.popRank.getShardDistribution()
```

#### Sharding db.popRankTech
All of db.popRankTech is assigned to dbms2shard.

```
mongos> db.popRankTech.createIndex({"id": 1})
mongos> sh.shardCollection("ddbs.popRankTech", {"id": 1})
mongos> sh.disableBalancing("ddbs.popRankTech")
mongos> sh.addShardTag("dbms2rs", "POPTECH")
mongos> sh.addTagRange(
            "ddbs.popRankTech",
            {"id": MinKey},
            {"id": MaxKey},
            "POPTECH"
        )
mongos> sh.enableBalancing("ddbs.popRankTech")
mongos> sh.status()
mongos> db.popRankTech.getShardDistribution()
```

#### Sharding db.popRankSci
Now, we want to assign all db.popRankSci to dbms1shard, and replicate do the same for dbms2shard.
First, let's make a copy db.popRankSci2.

```
mongos> db.popRankSci.find().forEach( function(doc) { db.popRankSci2.insert(doc) })
```

Then, we apply sharding for both copies.

For db.popRankSci, assign to dbms1shard.
```
mongos> db.popRankSci.createIndex({"id": 1})
mongos> sh.shardCollection("ddbs.popRankSci", {"id": 1})
mongos> sh.disableBalancing("ddbs.popRankSci")
mongos> sh.addShardTag("dbms1rs", "POPSCI")
mongos> sh.addTagRange(
            "ddbs.popRankSci",
            {"id": MinKey},
            {"id": MaxKey},
            "POPSCI"
        )
mongos> sh.enableBalancing("ddbs.popRankSci")
mongos> sh.status()
mongos> db.popRankSci.getShardDistribution()
```

For db.popRankSci2, assign to dbms2shard.
```
mongos> db.popRankSci2.createIndex({"id": 1})
mongos> sh.shardCollection("ddbs.popRankSci2", {"id": 1})
mongos> sh.disableBalancing("ddbs.popRankSci2")
mongos> sh.addShardTag("dbms2rs", "POPSCI2")
mongos> sh.addTagRange(
            "ddbs.popRankSci2",
            {"id": MinKey},
            {"id": MaxKey},
            "POPSCI2"
        )
mongos> sh.enableBalancing("ddbs.popRankSci2")
mongos> sh.status()
mongos> db.popRankSci2.getShardDistribution()
```

## Summary

At this point, we have several collections that are sharded and residing on dbms1shard and dbms2shard, and several that are temporal and reside on the mongos server,

| Collection  | Sharded to dbms1_shard | Sharded to dbms2_shard |
| ------------- | ------------- | ------------- |
| user  | BJ  | HK |
| article  | SCI  | TECH |
| articlesci | - | SCI2 |
| read_reg | BJ | HK |
| beread | SCI | TECH |
| bereadsci | - | SCI2 |
| popRank | - | POPALL |
| popRankSci | POPSCI | - |
| popRankSci2 | - | POPSCI2 |
| popRankTech | - | POPTECH |

Unsharded temporary collections are:
- uid_reg
- art_cat_ts
- read
- read_cat
- popRankMth
- popRankWk
- popRankDay
- popRankSciMth
- popRankSciWk
- popRankSciDay
- popRankTechMth
- popRankTechWk
- popRankTechDay