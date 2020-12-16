# Load, shard, and populate collections according to task requirements

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