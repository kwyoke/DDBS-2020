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

### See executive_program/ for quick setup
Inside executive_program/, we created a Makefile that compiles all the required bash commands to set up all docker containers, populating and sharding collections, and storing multimedia data. More details on how to run the Makefile can be found inside the directory. 

### See mongoshell_tutorial/ for full tutorial and explanation

Inside mongoshell_tutorial/, we provided detailed instructions and explanations on how to set up the docker containers and shard clusters, how to populate and shard the collections, how to automatically refresh data when there are modifications made to other related collections, and how to store and view multimedia data using GridFS.