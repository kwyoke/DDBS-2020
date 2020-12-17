import pymongo
from pymongo import MongoClient
from datetime import datetime

client = MongoClient('mongodb://192.168.1.152:60000/')
db = client.ddbs

with db.read.watch(
        [{'$match': {'operationType': 'insert'}}]) as stream:
        # can reasonably assume to only watch for inserts because read record cannot be undone or edited
    for change in stream:
        change = change['fullDocument']
        print(change)

        #################### update db.beread ####################
        doc = db.beread.find_one({"_id": change['aid']})

        readNum = int(doc['readNum']) + int(change['readOrNot'])
        readUidList = set(doc['readUidList'])
        if int(change['readOrNot']) and (change['uid'] not in readUidList):
            readUidList = readUidList.append(change['uid'])

        commentNum = int(doc['commentNum']) + int(change['commentOrNot'])
        commentUidList = list(doc['commentUidList'])
        if int(change['commentOrNot']) and (change['uid'] not in commentUidList):
            commentUidList = commentUidList.append(change['uid'])

        agreeNum = int(doc['agreeNum']) + int(change['agreeOrNot'])
        agreeUidList = list(doc['agreeUidList'])
        if int(change['agreeOrNot']) and (change['agreeOrNot'] not in agreeUidList):
            agreeUidList = agreeUidList.append(change['uid'])

        shareNum = int(doc['shareNum']) + int(change['shareOrNot'])
        shareUidList = list(doc['shareUidList'])
        if int(change['shareOrNot']) and (change['uid'] not in shareUidList):
            shareUidList = shareUidList.append(change['uid'])

        beread_dict = {
            "_id": doc['_id'],
            "timestamp": doc['timestamp'],
            "aid": doc['aid'],
            "readNum": readNum,
            "readUidList": readUidList,
            "commentNum": commentNum,
            "commentUidList": commentUidList,
            "agreeNum": agreeNum,
            "agreeUidList": agreeUidList,
            "shareNum": shareNum,
            "shareUidList": shareUidList
        }

        print(beread_dict)

        db.beread.replace_one({"_id": change['aid']}, beread_dict)

        ################# update db.bereadsci ######################
        if change['category'] == "science":

            doc = db.bereadsci.find_one({"_id": change['aid']})

            readNum = int(doc['readNum']) + int(change['readOrNot'])
            readUidList = set(doc['readUidList'])
            if int(change['readOrNot']) and (change['uid'] not in readUidList):
                readUidList = readUidList.append(change['uid'])

            commentNum = int(doc['commentNum']) + int(change['commentOrNot'])
            commentUidList = list(doc['commentUidList'])
            if int(change['commentOrNot']) and (change['uid'] not in commentUidList):
                commentUidList = commentUidList.append(change['uid'])

            agreeNum = int(doc['agreeNum']) + int(change['agreeOrNot'])
            agreeUidList = list(doc['agreeUidList'])
            if int(change['agreeOrNot']) and (change['agreeOrNot'] not in agreeUidList):
                agreeUidList = agreeUidList.append(change['uid'])

            shareNum = int(doc['shareNum']) + int(change['shareOrNot'])
            shareUidList = list(doc['shareUidList'])
            if int(change['shareOrNot']) and (change['uid'] not in shareUidList):
                shareUidList = shareUidList.append(change['uid'])

            bereadsci_dict = {
                "_id": doc['_id'],
                "timestamp": doc['timestamp'],
                "aid": doc['aid'],
                "readNum": readNum,
                "readUidList": readUidList,
                "commentNum": commentNum,
                "commentUidList": commentUidList,
                "agreeNum": agreeNum,
                "agreeUidList": agreeUidList,
                "shareNum": shareNum,
                "shareUidList": shareUidList
            }

            db.bereadsci.replace_one({"_id": change['aid']}, bereadsci_dict)

        ################ update db.popRank ######################
        # retrieve db.beread documents with read timestamps in the same month as change doc
        month_change = datetime.fromtimestamp(int(change['timestamp'][:-3])).month
        week_change = datetime.fromtimestamp(int(change['timestamp'][:-3])).week
        day_change = datetime.fromtimestamp(int(change['timestamp'][:-3])).timetuple().tm_yday
        cursor_docs = db.read.find({ "$expr": { "$eq": [{ "$month": {"$toDate": {"$toLong": "$timestamp"}}}, month_change]}})

        # aggregate these document selection to get newest month, week, day popularity scores
        art_popScore_mth = {}
        art_popScore_wk = {}
        art_popScore_day = {}
        for doc in cursor_docs:
            aid = doc['aid']
            if (aid not in art_popScore_mth.keys):
                art_popScore_mth[aid] = 0
            art_popScore_mth[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

            wk = datetime.fromtimestamp(int(doc['timestamp'][:-3])).week
            if (wk == week_change):
                if (aid not in art_popScore_wk.keys):
                    art_popScore_wk[aid] = 0
                art_popScore_wk[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

            day = datetime.fromtimestamp(int(doc['timestamp'][:-3])).timetuple().tm_yday
            if (day == day_change):
                if (aid not in art_popScore_day.keys):
                    art_popScore_day[aid] = 0
                art_popScore_day[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

        art_popScore_mth = sorted(art_popScore_mth.items(), key=lambda x: x[1], reverse=True)
        art_popScore_wk = sorted(art_popScore_wk.items(), key=lambda x: x[1], reverse=True)
        art_popScore_day = sorted(art_popScore_day.items(), key=lambda x: x[1], reverse=True)

        top5_mth = list(art_popScore_mth.keys[:5])
        top5_wk = list(art_popScore_wk.keys[:5])  
        top5_day = list(art_popScore_day.keys[:5])  


