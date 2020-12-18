import pymongo
from pymongo import MongoClient
from datetime import datetime
import datetime as dt

client = MongoClient('mongodb://192.168.1.152:60000/')
db = client.ddbs

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
        isodate = datetime.fromtimestamp(int(change['timestamp'][:-3])).isocalendar()
        month_change = isodate[0]
        week_change = isodate[1]
        day_change = datetime.fromtimestamp(int(change['timestamp'][:-3])).timetuple().tm_yday
        cursor_docs = db.read.find({ "$expr": { "$eq": [{ "$month": {"$toDate": {"$toLong": "$timestamp"}}}, month_change]}})

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
            print("doc", doc)
            aid = doc['aid']

            ########################## update popRank ###############################
            if (aid not in art_popScore_mth.keys):
                art_popScore_mth[aid] = 0
                ts_mth = doc['timestamp']
            art_popScore_mth[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

            wk = datetime.fromtimestamp(int(doc['timestamp'][:-3])).week
            if (wk == week_change):
                if (aid not in art_popScore_wk.keys):
                    art_popScore_wk[aid] = 0
                    ts_wk = doc['timestamp']
                art_popScore_wk[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

            day = datetime.fromtimestamp(int(doc['timestamp'][:-3])).timetuple().tm_yday
            if (day == day_change):
                if (aid not in art_popScore_day.keys):
                    art_popScore_day[aid] = 0
                    ts_day = doc['timestamp']
                art_popScore_day[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

            ##################### update science poprank ############################
            if (change['category'] == "science") and (doc['category'] == "science"):
                if (aid not in art_popScoreSci_mth.keys):
                    art_popScoreSci_mth[aid] = 0
                art_popScoreSci_mth[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

                if (wk == week_change):
                    if (aid not in art_popScoreSci_wk.keys):
                        art_popScoreSci_wk[aid] = 0
                    art_popScoreSci_wk[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

                if (day == day_change):
                    if (aid not in art_popScoreSci_day.keys):
                        art_popScoreSci_day[aid] = 0
                    art_popScoreSci_day[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

            ##################### update technology poprank ############################
            if (change['category'] == "technology") and (doc['category'] == "technology"):
                if (aid not in art_popScoreTech_mth.keys):
                    art_popScoreTech_mth[aid] = 0
                art_popScoreTech_mth[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

                if (wk == week_change):
                    if (aid not in art_popScoreTech_wk.keys):
                        art_popScoreTech_wk[aid] = 0
                    art_popScoreTech_wk[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

                if (day == day_change):
                    if (aid not in art_popScoreTech_day.keys):
                        art_popScoreTech_day[aid] = 0
                    art_popScoreTech_day[aid] += int(doc['readOrNot']) + int(doc['commentOrNot']) + int(doc['agreeOrNot']) + int(doc['shareOrNot'])

        ############ update popRank ###################
        art_popScore_mth = sorted(art_popScore_mth.items(), key=lambda x: x[1], reverse=True)
        art_popScore_wk = sorted(art_popScore_wk.items(), key=lambda x: x[1], reverse=True)
        art_popScore_day = sorted(art_popScore_day.items(), key=lambda x: x[1], reverse=True)

        top5_mth = list(art_popScore_mth[:5])
        top5_wk = list(art_popScore_wk[:5])  
        top5_day = list(art_popScore_day[:5])  

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

        db.popRank.replace_one({"_id": popMth_dict["_id"]}, popMth_dict)
        db.popRank.replace_one({"_id": popWk_dict["_id"]}, popWk_dict)
        db.popRank.replace_one({"_id": popDay_dict["_id"]}, popDay_dict)

        if change['category'] == "science":
            ############ update popRankSci/ popRankSci2 ###################
            art_popScore_mth = sorted(art_popScoreSci_mth.items(), key=lambda x: x[1], reverse=True)
            art_popScore_wk = sorted(art_popScoreSci_wk.items(), key=lambda x: x[1], reverse=True)
            art_popScore_day = sorted(art_popScoreSci_day.items(), key=lambda x: x[1], reverse=True)

            top5_mth = list(art_popScore_mth[:5])
            top5_wk = list(art_popScore_wk[:5])  
            top5_day = list(art_popScore_day[:5])  

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

            db.popRankSci.replace_one({"_id": popMth_dict["_id"]}, popMth_dict)
            db.popRankSci.replace_one({"_id": popWk_dict["_id"]}, popWk_dict)
            db.popRankSci.replace_one({"_id": popDay_dict["_id"]}, popDay_dict)

            db.popRankSci2.replace_one({"_id": popMth_dict["_id"]}, popMth_dict)
            db.popRankSci2.replace_one({"_id": popWk_dict["_id"]}, popWk_dict)
            db.popRankSci2.replace_one({"_id": popDay_dict["_id"]}, popDay_dict)

        if change['category'] == "technology":
            ############ update popRankTech ###################
            art_popScore_mth = sorted(art_popScoreTech_mth.items(), key=lambda x: x[1], reverse=True)
            art_popScore_wk = sorted(art_popScoreTech_wk.items(), key=lambda x: x[1], reverse=True)
            art_popScore_day = sorted(art_popScoreTech_day.items(), key=lambda x: x[1], reverse=True)

            top5_mth = list(art_popScore_mth[:5])
            top5_wk = list(art_popScore_wk[:5])  
            top5_day = list(art_popScore_day[:5])  

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

            db.popRankSci.replace_one({"_id": popMth_dict["_id"]}, popMth_dict)
            db.popRankSci.replace_one({"_id": popWk_dict["_id"]}, popWk_dict)
            db.popRankSci.replace_one({"_id": popDay_dict["_id"]}, popDay_dict)

            db.popRankSci2.replace_one({"_id": popMth_dict["_id"]}, popMth_dict)
            db.popRankSci2.replace_one({"_id": popWk_dict["_id"]}, popWk_dict)
            db.popRankSci2.replace_one({"_id": popDay_dict["_id"]}, popDay_dict)

