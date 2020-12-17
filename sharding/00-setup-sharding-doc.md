## Set up Sharding using Docker Containers

### Config servers
Start config servers (3 member replica set)
```
docker-compose -f config-server/docker-compose.yaml up -d
```
Initiate replica set

(somehow localhost doesn't work, so need to find local IP address of machine, e.g. hostname -I)
```
mongo mongodb://192.168.1.152:40001
```
```
rs.initiate(
  {
    _id: "cfgrs",
    configsvr: true,
    members: [
      { _id : 0, host : "192.168.1.152:40001" },
      { _id : 1, host : "192.168.1.152:40002" },
      { _id : 2, host : "192.168.1.152:40003" }
    ]
  }
)

rs.status()
```

### dbms1 shard servers
Start dbms1 shard servers (single member replicaset)
```
docker-compose -f dbms1shard/docker-compose.yaml up -d
```
Initiate replica set
```
mongo mongodb://192.168.1.152:50001
```
```
rs.initiate(
  {
    _id: "dbms1rs",
    members: [
      { _id : 0, host : "192.168.1.152:50001" }
    ]
  }
)

rs.status()
```

### Mongos Router
Start mongos query router
```
docker-compose -f mongos/docker-compose.yaml up -d
```

### Add shard to the cluster
Connect to mongos
```
mongo mongodb://192.168.1.152:60000
```
Add shard
```
mongos> sh.addShard("dbms1rs/192.168.1.152:50001")
mongos> sh.status()
```
## Adding another shard
### dbms2 shard servers
Start shard 2 servers (single member replicaset)
```
docker-compose -f dbms2shard/docker-compose.yaml up -d
```
Initiate replica set
```
mongo mongodb://192.168.1.152:50002
```
```
rs.initiate(
  {
    _id: "dbms2rs",
    members: [
      { _id : 0, host : "192.168.1.152:50002" }
    ]
  }
)

rs.status()
```
### Add shard to the cluster
Connect to mongos
```
mongo mongodb://192.168.1.152:60000
```
Add shard
```
mongos> sh.addShard("dbms2rs/192.168.1.152:50002")
mongos> sh.status()
```

## Adding another shard
### Grid1 shard servers
Start grid1 shard servers (single member replicaset)
```
docker-compose -f grid1shard/docker-compose.yaml up -d
```
Initiate replica set
```
mongo mongodb://192.168.1.152:50003
```
```
rs.initiate(
  {
    _id: "grid1rs",
    members: [
      { _id : 0, host : "192.168.1.152:50003" },
    ]
  }
)

rs.status()
```
### Add shard to the cluster
Connect to mongos
```
mongo mongodb://192.168.1.152:60000
```
Add shard
```
mongos> sh.addShard("grid1rs/192.168.1.152:50003")
mongos> sh.status()
```

## Adding another shard
### Grid2 shard servers
Start grid2 shard servers (single member replicaset)
```
docker-compose -f grid2shard/docker-compose.yaml up -d
```
Initiate replica set
```
mongo mongodb://192.168.1.152:50004
```
```
rs.initiate(
  {
    _id: "grid2rs",
    members: [
      { _id : 0, host : "192.168.1.152:50004" }
    ]
  }
)

rs.status()
```
### Add shard to the cluster
Connect to mongos
```
mongo mongodb://192.168.1.152:60000
```
Add shard
```
mongos> sh.addShard("grid2rs/192.168.1.152:50004")
mongos> sh.status()
```