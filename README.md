# DDBS Project 2020

In this project, we demonstrate how to set up and manage a distributed database system using MongoDB. We are given 10GB of structured data in the form of three JSON files (user.dat, article.dat, read.dat) and also unstructured data in the form of jpg, flv and txt files associated with each article. We are required to populate three more collections (db.read, db.beread, db.popRank) by aggregating the given raw data files. We then distribute each collection across two DBMS sites, dbms1shard and dbms2shard, which are simulated by docker containers. The unstructured multimedia data are distributed in two other GridFS servers, grid1shard and grid2shard. All sharded collections can be loaded into the mongos server which acts like the data centre, where queries， inserts and updates on each collection can be made even though the collections reside on other servers. The status of the shard clusters can be easily monitored using MongoDB's utilities.

## Documentation organisation

### Generating 10GB of dummy data to work on
Run the sharding/proj_data/genTable_mongoDB10G.py script to generate the three structured data files: user.dat, article.dat, read.dat, and the unstructured multimedia data which are stored in the sharding/proj_data/articles directory.

### Setting up docker containers to simulate different machines for data distribution

We set up 8 docker containers in total: 3 config servers in a replica set, 1 mongos server which is the router and acts like the data centre that coordinates all collections, 2 dbms server shards for distributing structured data and 2 GridFS server shards for distributing multimedia data. MongoDB supports replica sets which should contain at least a cluster of three servers: one primary and two secondary, but due to lack of computer space, we decided to just have single servers instead of replica sets of DBMS and GridFS shards. The configuration of each docker container are specified the docker-compose.yaml files in sharding/config-server/, sharding/dbms1shard/, sharding/dbms2shard/, sharding/grid1shard/, sharding/grid2shard/, sharding/mongos/. The detailed instructions of setting up the docker containers for sharding can be found in sharding/00-setup-sharding-doc.md. This part is based on the following  [Associated YouTube Playlist](https://www.youtube.com/watch?v=LBthwZDRR-c&list=PL34sAs7_26wPvZJqUJhjyNtm7UedWR8Ps).

![Screenshot of docker containers setup](/pics/dockersetup.png?raw=true "Optional Title")