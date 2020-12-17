### Sharding for gridfs
This is just the standard sharding procedure like what we did for db.user.
```
mongos> db.fs.chunks.createIndex({"files_id": 1})
mongos> sh.shardCollection("ddbs.fs.chunks", {"files_id": "hashed"})
mongos> sh.addShardTag("grid1rs", "MEDIA")
mongos> sh.addTagRange(
            "ddbs.fs.chunks",
            {"files_id": MinKey},
            {"files_id": MaxKey},
            "MEDIA"
        )
mongos> sh.addShardTag("grid2rs", "MEDIA")
mongos> sh.addTagRange(
            "ddbs.fs.chunks",
            {"files_id": MinKey},
            {"files_id": MaxKey},
            "MEDIA"
        )
mongos> sh.enableBalancing("ddbs.fs.chunks")
mongos> sh.status()
mongos> db.fs.chunks.getShardDistribution()
```