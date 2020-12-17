### Sharding for gridfs
This is just the standard sharding procedure like what we did for db.user.
```
mongos> db.fs.chunks.createIndex({"region": 1, "id": 1})
mongos> sh.shardCollection("ddbs.read", {"region": 1, "id": 1})
mongos> sh.disableBalancing("ddbs.read")
mongos> sh.addShardTag("dbms1rs", "BJ")
mongos> sh.addTagRange(
            "ddbs.read",
            {"region": "Beijing", "id": MinKey},
            {"region": "Beijing", "id": MaxKey},
            "BJ"
        )
mongos> sh.addShardTag("dbms2rs", "HK")
mongos> sh.addTagRange(
            "ddbs.read",
            {"region": "Hong Kong", "id": MinKey},
            {"region": "Hong Kong", "id": MaxKey},
            "HK"
        )
mongos> sh.enableBalancing("ddbs.read")
mongos> sh.status()
mongos> db.read.getShardDistribution()
```