#！/bin/bash

for DIR in proj_data/articles/*/
do
    for FILE in "${DIR}"*
        do

        BASEFILENAME=$(basename $FILE)
        mongofiles --host=192.168.1.152:60000 --local=$FILE -d=ddbs put $BASEFILENAME 
    done      
done