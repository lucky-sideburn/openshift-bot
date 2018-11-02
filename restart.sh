kill $(ps -ef | grep openshift-bot | grep -v grep | awk '{ print $2 }')
python openshift-bot.py
