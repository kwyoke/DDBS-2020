# THINGS TO SHOW IN DEMO

## DOCKER CONTAINERS AND MEMORY (20s)
```
docker ps
free -h
```

## MONGOS SHELL, SHOW BEREAD, POPRANK (40s)
```
docker exec -it mongos bash
mongo
```
```
mongos> use ddbs
mongos> show collections
mongos> db.user.findOne()
mongos> db.beread.findOne()
mongos> db.popRank.findOne()
```

## SHARDING (1min 30s)
```
mongos> sh.status()
mongos> db.user.getShardDistribution()
mongos> db.user.insert({"uid": "12345678", "region": "Beijing"})
mongos> db.user.getShardDistribution()
```
### ENTER dbms1shard (30s)
```
docker exec -it dbms1rs bash
mongo
```
```
mongos> use ddbs
mongos> db.user.count()
```
## Watch and update (40s)
```
python auto_refresh_onread.py
```
```
mongos> db.beread.insert(
			{ "_id" : "123456", "category" : "technology", "timestamp" : "1506000008604", "readNum" : 0, "readUidList" : [ ], "commentNum" : 0, "commentUidList" : [ ], "agreeNum" : 0, "agreeUidList" : [ ], "shareNum" : "0", "shareUidList" : [], "aid" : "a123456" }
			)

mongos> db.read.insert({
			"_id" : ObjectId("5fd9644ebaedf1c547ffffff"),
			"timestamp" : "1506346147000",
			"id" : "r123456789",
			"uid" : "12345",
			"aid" : "123456",
			"readOrNot" : "0",
			"readTimeLength" : "0",
			"readSequence" : "0",
			"agreeOrNot" : "0",
			"commentOrNot" : "0",
			"shareOrNot" : "1",
			"commentDetail" : "",
			"region" : "Beijing",
			"category" : "technology"
		})
```

## GET IMAGE FROM GRIDFS (40s)
```
mongos> db.article.find({"aid": "5"})
```
```
mongofiles --host=192.168.1.152:60000 -d=ddbs get xxx.jpg
xdg-open xxx.jpg
```