# Setting up auto refreshing of derived collections

For this project, db.user, db.article, and db.read are the raw main collections which will receive insertions, deletions and updates, while db.articlesci, db.beread, db.bereadsci, db.popRank, db.popRankSci, db.popRankSci2 and db.popRankTech are computed from these three main collections. Therefore, we need to be able to automatically refresh the derived collections when there are insertions, updates, and removals from db.user, db.article and db.read. 

Specifically, the refreshes to be performed are summarised as below:

| Collection to watch  | Collection to update | Update to perform |
| ------------- | ------------- | ------------- |
| article  | articlesci  | insert document if category = "science" |
| read  | beread, bereadsci | update fields: {readNum, readUidList, commentNum, commentUidList, agreeNum, agreeUidList, shareNum, shareUidList} for relevant documents with aid matching documents inserted into db.read |
| read | popRank, popRankSci, popRankTech | filter records in db.read with timestamps in the same month as new read, calculate popScoreAgg for each aid within the filtered records for each month/week/day, put top 5 for each month/week/day in arrays, form new documents and insert, replacing if timestamp overlaps |

We watch the db.article and db.read collections for changes using MongoDB's change stream's cursor db.collection.watch() and make the respective updates to the derived collections using a python script running in the background (python script runs on local terminal).

Install pymongo.
```
python -m pip install pymongo
```

Using pymongo, we have to connect to the mongos server to access the ddbs database. Inside the python script, we have to include the connection command at the start of the script：
```
import pymongo
from pymongo import MongoClient

client = MongoClient('mongodb://192.168.1.152:60000/') #connect to host containing mongos router
db = client.ddbs
```

## Auto refresh on changes to db.article

We automatically refresh db.articlesci when changes to db.article involves the "science" category. 

Run the python script auto_refresh_onarticle.py in your local terminal to start watching the db.article collection.
```
python auto_refresh_onarticle.py
```
The code in the python script to update db.articlesci upon changes in db.article looks like this: 
```
# python script

with db.article.watch(
        [{'$match': {'fullDocument.category': 'science'}}]) as stream:
    for change in stream:
        print(change)
        db.article.aggregate([
            {"$match": {"category": "science"}},
            {"$merge": {"into": "articlesci", "whenMatched":"replace"}}
        ])
```


## Auto refresh on changes to db.read

We assume that changes to db.read are insertions only which is reasonable as it would not make sense to update a read record that happened already. When there are insertions to db.read, we update documents in db.beread and db.bereadsci (by modifying fields), and we either replace or insert new documents aggregating the most popular articles in the most recent month, week and day.

Run the python script auto_refresh_onread.py in another terminal of your local computer simultaneously with auto_refresh_onarticle.py in the background. Currently, MongoDB does not support watching multiple collections in the same script so I have separated them in two scripts.

```
python auto_refresh_onarticle.py
```

The code to update db.beread, db.bereadsci, db.popRank, db.popRankTech, db.popRankSci and db.popRankSci2 in the python script are shown below:
```
with db.read.watch(
        [{'$match': {'operationType': 'insert'}}]) as stream:
        # can reasonably assume to only watch for inserts because read record cannot be undone or edited
    for change in stream:
        change = change['fullDocument']
        print(change)

        #################### update db.beread/ db.bereadsci ####################
        doc = db.beread.find_one({"_id": change['aid']})

        readNum = int(doc['readNum']) + int(change['readOrNot'])
        readUidList = list(doc['readUidList'])
        if int(change['readOrNot']) > 0 and (change['uid'] not in readUidList):
            readUidList.append(change['uid'])

        commentNum = int(doc['commentNum']) + int(change['commentOrNot'])
        commentUidList = list(doc['commentUidList'])
        if int(change['commentOrNot']) > 0 and (change['uid'] not in commentUidList):
            commentUidList.append(change['uid'])

        agreeNum = int(doc['agreeNum']) + int(change['agreeOrNot'])
        agreeUidList = list(doc['agreeUidList'])
        if int(change['agreeOrNot']) > 0 and (change['agreeOrNot'] not in agreeUidList):
            agreeUidList.append(change['uid'])

        shareNum = int(doc['shareNum']) + int(change['shareOrNot'])
        shareUidList = list(doc['shareUidList'])
        if int(change['shareOrNot']) > 0 and (change['uid'] not in shareUidList):
            shareUidList.append(str(change['uid']))


        beread_dict = {
            "_id": doc['_id'],
            "category": doc['category'],
            "timestamp": doc['timestamp'],
            "readNum": readNum,
            "readUidList": readUidList,
            "commentNum": commentNum,
            "commentUidList": commentUidList,
            "agreeNum": agreeNum,
            "agreeUidList": agreeUidList,
            "shareNum": shareNum,
            "shareUidList": shareUidList,
            "aid": doc['aid'],
        }

        db.beread.replace_one({"_id": change['aid']}, beread_dict)

        if change['category'] == "science":
            db.bereadsci.replace_one({"_id": change['aid']}, beread_dict)


        ################ update popRank, popRankSci,popRankSci2, popRankTech ######################
        # retrieve db.read documents with read timestamps in the same month as change doc
        date_change = datetime.fromtimestamp(int(change['timestamp'][:-3]))
        year_change = date_change.year
        month_change = date_change.month
        week_change = date_change.isocalendar()[1]
        day_change = date_change.timetuple().tm_yday

        cursor_docs = db.read.find( { "$and": [{ "$expr": { "$eq": [{ "$month": {"$toDate": {"$toLong": "$timestamp"}}}, month_change]}},
                                               { "$expr": { "$eq": [{ "$year": {"$toDate": {"$toLong": "$timestamp"}}}, year_change]}} ]})

        # aggregate these document selection to get newest month, week, day popularity scores
        art_popScore_mth = {}
        art_popScore_wk = {}
        art_popScore_day = {}

        art_popScoreSci_mth = {}
        art_popScoreSci_wk = {}
        art_popScoreSci_day = {}

        art_popScoreTech_mth = {}
        art_popScoreTech_wk = {}
        art_popScoreTech_day = {}
        for doc in cursor_docs:
            aid = doc['aid']

            date_doc = datetime.fromtimestamp(int(doc['timestamp'][:-3]))
            wk = date_doc.isocalendar()[1]
            day = date_doc.timetuple().tm_yday

            ########################## update popRank ###############################
            if (aid not in art_popScore_mth):
                art_popScore_mth[aid] = 0
                ts_mth = doc['timestamp']
            art_popScore_mth[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

            if (wk == week_change):
                if (aid not in art_popScore_wk):
                    art_popScore_wk[aid] = 0
                    ts_wk = doc['timestamp']
                art_popScore_wk[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

            if (day == day_change):
                if (aid not in art_popScore_day):
                    art_popScore_day[aid] = 0
                    ts_day = doc['timestamp']
                art_popScore_day[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

            ##################### update science poprank ############################
            if (change['category'] == "science") and (doc['category'] == "science"):
                if (aid not in art_popScoreSci_mth):
                    art_popScoreSci_mth[aid] = 0
                art_popScoreSci_mth[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

                if (wk == week_change):
                    if (aid not in art_popScoreSci_wk):
                        art_popScoreSci_wk[aid] = 0
                    art_popScoreSci_wk[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

                if (day == day_change):
                    if (aid not in art_popScoreSci_day):
                        art_popScoreSci_day[aid] = 0
                    art_popScoreSci_day[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

            ##################### update technology poprank ############################
            if (change['category'] == "technology") and (doc['category'] == "technology"):
                if (aid not in art_popScoreTech_mth):
                    art_popScoreTech_mth[aid] = 0
                art_popScoreTech_mth[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

                if (wk == week_change):
                    if (aid not in art_popScoreTech_wk):
                        art_popScoreTech_wk[aid] = 0
                    art_popScoreTech_wk[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

                if (day == day_change):
                    if (aid not in art_popScoreTech_day):
                        art_popScoreTech_day[aid] = 0
                    art_popScoreTech_day[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

        ############ update popRank ###################
        art_popScore_mth = np.array(sorted(art_popScore_mth.items(), key=lambda x: x[1], reverse=True))
        art_popScore_wk = np.array(sorted(art_popScore_wk.items(), key=lambda x: x[1], reverse=True))
        art_popScore_day = np.array(sorted(art_popScore_day.items(), key=lambda x: x[1], reverse=True))

        top5_mth = list(art_popScore_mth[:5, 0])
        top5_wk = list(art_popScore_wk[:5, 0])  
        top5_day = list(art_popScore_day[:5, 0])  

        popMth_dict = {
            "_id": "m" + str(ts_mth),
            "timestamp": ts_mth,
            "articleAidList": top5_mth,
            "temporalGranularity:": "monthly"
        }

        popWk_dict = {
            "_id": "w" + str(ts_wk),
            "timestamp": ts_wk,
            "articleAidList": top5_wk,
            "temporalGranularity:": "weekly"
        }

        popDay_dict = {
            "_id": "d" + str(ts_day),
            "timestamp": ts_day,
            "articleAidList": top5_day,
            "temporalGranularity:": "daily"
        }


        db.popRank.replace_one({"_id": popMth_dict["_id"]}, popMth_dict, upsert=True)
        db.popRank.replace_one({"_id": popWk_dict["_id"]}, popWk_dict, upsert=True)
        db.popRank.replace_one({"_id": popDay_dict["_id"]}, popDay_dict, upsert=True)

        if change['category'] == "science":
            ############ update popRankSci/ popRankSci2 ###################
            art_popScore_mth = np.array(sorted(art_popScoreSci_mth.items(), key=lambda x: x[1], reverse=True))
            art_popScore_wk = np.array(sorted(art_popScoreSci_wk.items(), key=lambda x: x[1], reverse=True))
            art_popScore_day = np.array(sorted(art_popScoreSci_day.items(), key=lambda x: x[1], reverse=True))

            top5_mth = list(art_popScore_mth[:5, 0])
            top5_wk = list(art_popScore_wk[:5, 0])  
            top5_day = list(art_popScore_day[:5, 0])  

            popMth_dict = {
                "_id": "m" + str(ts_mth),
                "timestamp": ts_mth,
                "articleAidList": top5_mth,
                "temporalGranularity:": "monthly"
            }

            popWk_dict = {
                "_id": "w" + str(ts_wk),
                "timestamp": ts_wk,
                "articleAidList": top5_wk,
                "temporalGranularity:": "weekly"
            }

            popDay_dict = {
                "_id": "d" + str(ts_day),
                "timestamp": ts_day,
                "articleAidList": top5_day,
                "temporalGranularity:": "daily"
            }

            db.popRankSci.replace_one({"_id": popMth_dict["_id"]}, popMth_dict, { "upsert": "true"  })
            db.popRankSci.replace_one({"_id": popWk_dict["_id"]}, popWk_dict, { "upsert": "true" })
            db.popRankSci.replace_one({"_id": popDay_dict["_id"]}, popDay_dict, { "upsert": "true" })

            db.popRankSci2.replace_one({"_id": popMth_dict["_id"]}, popMth_dict, { "upsert": "true" })
            db.popRankSci2.replace_one({"_id": popWk_dict["_id"]}, popWk_dict, { "upsert": "true" })
            db.popRankSci2.replace_one({"_id": popDay_dict["_id"]}, popDay_dict, { "upsert": "true"  })

        if change['category'] == "technology":
            ############ update popRankTech ###################
            art_popScore_mth = np.array(sorted(art_popScoreTech_mth.items(), key=lambda x: x[1], reverse=True))
            art_popScore_wk = np.array(sorted(art_popScoreTech_wk.items(), key=lambda x: x[1], reverse=True))
            art_popScore_day = np.array(sorted(art_popScoreTech_day.items(), key=lambda x: x[1], reverse=True))

            top5_mth = list(art_popScore_mth[:5, 0])
            top5_wk = list(art_popScore_wk[:5, 0])  
            top5_day = list(art_popScore_day[:5, 0])  

            popMth_dict = {
                "_id": "m" + str(ts_mth),
                "timestamp": ts_mth,
                "articleAidList": top5_mth,
                "temporalGranularity:": "monthly"
            }

            popWk_dict = {
                "_id": "w" + str(ts_wk),
                "timestamp": ts_wk,
                "articleAidList": top5_wk,
                "temporalGranularity:": "weekly"
            }

            popDay_dict = {
                "_id": "d" + str(ts_day),
                "timestamp": ts_day,
                "articleAidList": top5_day,
                "temporalGranularity:": "daily"
            }

            print(popDay_dict)

            db.popRankTech.replace_one({"_id": popMth_dict["_id"]}, popMth_dict, upsert=True)
            db.popRankTech.replace_one({"_id": popWk_dict["_id"]}, popWk_dict, upsert=True)
            db.popRankTech.replace_one({"_id": popDay_dict["_id"]}, popDay_dict, upsert=True)
```

## Test out refreshing capability

### Test refreshing on db.article updates

Insert a dummy entry with "science" category into db.article. 

```
mongos> db.article.insert({
			"_id" : ObjectId("5fdb832f4fadf8e7f9ffffff"),
			"id" : "a654321",
			"timestamp" : "1506000000000",
			"aid" : "654321",
			"title" : "",
			"category" : "science",
			"abstract" : "",
			"articleTags" : "",
			"authors" : "",
			"language" : "zh",
			"text" : "",
			"image" : "",
			"video" : ""
		})
```
Check if db.articlesci is updated. Then remove the dummy changes.
```
mongos> db.articlesci.find({"aid": "654321"})
mongos> db.article.remove({"aid": "654321"})
mongos> db.articlesci.remove({"aid": "654321"})
```

### Test refreshing on db.read updates

Insert a dummy entry into db.beread first so that dummy updates will not corrupt the other documents.

```
mongos> db.beread.insert(
			{ "_id" : "123456", "category" : "technology", "timestamp" : "1506000008604", "readNum" : 0, "readUidList" : [ ], "commentNum" : 0, "commentUidList" : [ ], "agreeNum" : 0, "agreeUidList" : [ ], "shareNum" : "0", "shareUidList" : [], "aid" : "a123456" }
			)
```
Insert dummy entry into db.read with technology category.
```
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
Check updates in db.beread, db.popRank, db.popRankTech. Changes to db.popRank is not that obvious, so it is more convenient to observe the updates made as printed out by the python scripts.
```
mongos> db.beread.find({"_id": "123456"})
mongos> db.popRank.find({}).sort({"timestamp": -1}).limit(1)
mongos> db.popRankTech.find({}).sort({"timestamp": -1}).limit(1)
```
The auto_refresh.py script should print out the changes made, and the db.articlesci should be updated as well.