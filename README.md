# DDBS Project 2020

In this project, we demonstrate how to set up and manage a distributed database system using MongoDB. We are given 10GB of structured data in the form of three JSON files (user.dat, article.dat, read.dat) and also unstructured data in the form of jpg, flv and txt files associated with each article. We are required to populate three more collections (db.read, db.beread, db.popRank) by aggregating the given raw data files. We then distribute each collection across two DBMS sites, dbms1shard and dbms2shard, which are simulated by docker containers. The unstructured multimedia data are distributed in two other GridFS servers, grid1shard and grid2shard. All sharded collections can be loaded into the mongos server which acts like the data centre, where queries， inserts and updates on each collection can be made even though the collections reside on other servers. The status of the shard clusters can be easily monitored using MongoDB's utilities.

## Prerequisites to install
I implemented this project on a Ubuntu 18.04 machine, following instructions from [YouTube tutorial series for MongoDB](https://www.youtube.com/watch?v=LBthwZDRR-c&list=PL34sAs7_26wPvZJqUJhjyNtm7UedWR8Ps) to install MongoDB and docker. This tutorial series is also good for understanding the basics in MongoDB.

1. Follow the [official MongoDB documentation](https://docs.mongodb.com/manual/installation/#mongodb-community-edition-installation-tutorials) to install for your machine type. You will also need to install [mongofiles](https://docs.mongodb.com/database-tools/mongofiles/) if it does not come with your MongoDB installation.


2. Follow the [official Docker documentation](https://docs.docker.com/get-docker/) to install docker for your machine type. You will also need to install [docker-compose](https://docs.docker.com/compose/install/) if it does not come with the Docker installation.

3. Install [pymongo](https://pymongo.readthedocs.io/en/stable/installation.html) as we will be using python scripts to interact with the MongoDB collections.

4. (Optional) I used the command line throughout in this project, but MongoDB comes with GUIs like [MongoDB Compass](https://www.mongodb.com/products/compass) that would make MongoDB more user friendly, so you can install if you wish to.

## Demo
[![Watch the demo video to see DBMS in action](/pics/demostill.png?raw=true "Optional Title")](https://u.pcloud.link/publink/show?code=XZYrz8XZe9OFYT2EnWbEBBCyxOBTYbIVupkX)

## Documentation organisation

### Generating 10GB of dummy data to work on
Run the sharding/proj_data/genTable_mongoDB10G.py script to generate the three structured data files: user.dat, article.dat, read.dat, and the unstructured multimedia data which are stored in the sharding/proj_data/articles directory.

### Setting up docker containers to simulate different machines for data distribution (sharding)

We set up 8 docker containers in total: 3 config servers in a replica set, 1 mongos server which is the router and acts like the data centre that coordinates all collections, 2 DBMS server shards for distributing structured data and 2 GridFS server shards for distributing multimedia data. MongoDB supports replica sets which should contain at least a cluster of three servers: one primary and two secondary, but due to lack of computer space, we decided to just have single servers instead of replica sets of DBMS and GridFS shards. The configuration of each docker container are specified the docker-compose.yaml files. The detailed instructions of setting up the docker containers for sharding can be found in [00-setup-sharding-doc.md](https://github.com/kwyoke/DDBS-2020/blob/main/sharding/00-setup-sharding-doc.md). This part is based on this  [YouTube tutorial series for MongoDB](https://www.youtube.com/watch?v=LBthwZDRR-c&list=PL34sAs7_26wPvZJqUJhjyNtm7UedWR8Ps).

![Screenshot of docker containers setup](/pics/dockersetup.png?raw=true "Optional Title")

![Shard setup](/pics/shardsetup.jpeg?raw=true "Optional Title")

### Loading, sharding and populating stuctured collections
The collections db.user, db.article, db.read are sharded according to requirements, and the derived collections db.beread, db.popRank are populated by aggregating the three raw collections. The detailed instructions for loading, sharding and populating these collections can be found in [01_load_shard_populate_doc.md](https://github.com/kwyoke/DDBS-2020/blob/main/sharding/01_load_shard_populate_doc.md).

### Auto refreshing of derived collections when changes are made to raw collections
When there are insertions or updates to db.user, db.article and db.read, the derived collections db.beread and db.popRank also updates. Using pymongo and MongoDB's changestream utilities, we are able to constantly watch for changes and react to them accordingly. Detailed instructions can be found in [02_auto_refresh.md](https://github.com/kwyoke/DDBS-2020/blob/main/sharding/02_auto_refresh.md).

### Loading and sharding multimedia data in GridFS
The multimedia data is quite large, and is loaded into GridFS servers with the mongofiles utility (used from command line). Detailed instructions can be found in [03_gridfs.md](https://github.com/kwyoke/DDBS-2020/blob/main/sharding/03_gridfs.md). The multimedia data can then be easily retrieved from GridFS using the mongofiles utility.

### Monitoring of data distribution and server workload
Simply type in the mongos mongo shell "sh.status" to get an overall summary of each shard server, and db.article.getShardDistribution() to get the amount of documents distributed across different shards.

![sh status](/pics/shstatus.png)

![sh distrib](/pics/getsharddistribpng.png)