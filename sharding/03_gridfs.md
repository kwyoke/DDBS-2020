# Storing multimedia data in GridFS
The articles come with multimedia data that are not stored directly on our MongoDB DBMS servers due to their large size. Instead, our MongDB DBMS servers only store the filenames of the multimedia data, which are then used to retrieve the image data from other storage servers dedicated for multimedia data, which use the GridFS specification.

## Sharding for GridFS
We have two shard servers, grid1svr and grid2svr dedicated to storing multimedia data of articles. Before loading the multimedia to the data, we first set up sharding so that the (~10GB) worth of data will be distributed to the two server as it is uploaded to GridFS. GridFS is a specification for storing and retrieving large files of more than 16MB， which is perfect for our use case in storing image, video and text files data. We apply hashed sharding here to allow more even distribution of multimedia across the two shard servers. We traditionally used Hadoop as the storage server, but since it is easier to interface GridFS with MongoDB, we use GridFS.

GridFS automatically stores the data files in db.fs.chunks collection, and the filenames in db.fs.files collection. We will only shard the db.fs.chunks collection since it is very large, while db.fs.files will not be sharded and will remain on the mongos server.

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

## Uploading (10GB) of multimedia data to GridFS
The genTable_mongoDB10G.py script ran previously has generated 10GB of multimedia data stored in the articles directory with a specific file structure. Run the bash script bulk_store_multimedia.sh to store the data on the two GridFS servers. The bash script simply runs mongofiles which is a command line utility for interacting with GridFS.

Run bash script in the directory proj_mongodb/sharding/.
```
./bulk_store_multimedia.sh
```

mongodile command in bash script: 
```
# bulk_store_multimedia.sh bash script

for DIR in proj_data/articles/*/
do
    for FILE in "${DIR}"*
        do

        BASEFILENAME=$(basename $FILE)
        mongofiles --host=192.168.1.152:60000 --local=$FILE -d=ddbs put $BASEFILENAME 
    done      
done
```

Note that this might consume a lot of RAM, but I was able to do it with 16GB RAM with all my containers running. You should restart your computer after the multimedia data has finished uploading to clear your RAM.