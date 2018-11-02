#!/usr/local/bin/python
import os
import string
import random
import telegram
import logging
import requests
import configparser
import json
import time
from string import Template

from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler, Filters

config = configparser.ConfigParser()
config.read('./openshift-bot.ini')

OC_TOKEN        = config['OPENSHIFT']['Token']
OC_NAMESPACE    = config['OPENSHIFT']['Namespace']
OC_ENDPOINT     = config['OPENSHIFT']['Endpoint']
DOCKER_REGISTRY = config['DOCKER']['Host']
BOT_TOKEN       = config['BOT']['Token']
DATA_DIR        = config['BOT']['Data_dir']
headers = { }
headers['Authorization'] = "Bearer " + OC_TOKEN
headers['Accept'] = 'application/json'
headers['Content-Type'] = 'application/json'

def create_route(app_name,app_dir):
  route_request = "https://%s/apis/route.openshift.io/v1/namespaces/%s/routes" % (OC_ENDPOINT,OC_NAMESPACE)
  host = app_name + '.' + '94.23.211.122.nip.io'
  s = Template('{"kind": "Route", "spec": {"path": "/", "host": "$host", "port": {"targetPort": "8080-tcp"}, "wildcardPolicy": "None", "to": {"kind": "Service", "name": "$name", "weight": 100}}, "apiVersion": "route.openshift.io/v1", "metadata": {"labels": {"app": "$name"}, "namespace": "$namespace", "name": "$name"}}')
  r = requests.post(route_request,data=s.substitute(name=app_name,host=host,namespace=OC_NAMESPACE),verify=False,headers=headers)
  print r.text

def build_completed(app_name):
  build_config_request = "https://%s/apis/build.openshift.io/v1/namespaces/%s/buildconfigs"  % (OC_ENDPOINT,OC_NAMESPACE)
  build_request = "https://%s/apis/build.openshift.io/v1/namespaces/%s/builds/%s-" % (OC_ENDPOINT,OC_NAMESPACE,app_name)

  r = requests.get(build_config_request,verify=False,headers=headers)
  buildconfigs = json.loads(r.text)
  print type(buildconfigs['items'])
  for buildconfig in buildconfigs['items']:
    if buildconfig['metadata']['name'] == app_name:
      build_request = requests.get(build_request + str(buildconfig['status']['lastVersion']),verify=False,headers=headers) 
      build = json.loads(build_request.text)
      if build['status']['phase'] == 'Complete':
        return buildconfig['status']['lastVersion']
      else:
        return False

def random_generator(size=6, chars=string.ascii_lowercase + string.digits):
  return ''.join(random.choice(chars) for x in range(size))

def start(bot, update):
  bot.send_photo(chat_id=update.message.chat_id, photo=open('openshift.png', 'rb'))
  bot.send_message(chat_id=update.message.chat_id, text="I'm the Openshift Bot! Please take a picture and I will create a pod for exposing your photo through the internet!")

def echo(bot, update):
  bot.send_message(chat_id=update.message.chat_id, text=update.message.text)

def photo_handler(bot, update):
  app_name = "ocbot" + random_generator()
  app_dir = os.path.join(DATA_DIR,app_name)
  app_log_file = os.path.join(app_dir,'build.log')

  os.system("cp -r demo-image " + app_dir)

  print update.message.text
  file = bot.getFile(update.message.photo[-1])
  file.download(app_dir +'/from_telegram.jpg')
  build_docker_image(app_name,app_dir,app_log_file,bot,update)
  bot.send_message(chat_id=update.message.chat_id, text="Waiting for complete build of " + app_name)
   
  build_latest_version = False 
 
  while not build_latest_version:
    build_latest_version  = build_completed(app_name)
    time.sleep(2)
  os.system("oc logs build/" + app_name + "-" + str(build_latest_version) + "&>" + app_log_file)
  bot.send_document(chat_id=update.message.chat_id, document=open(app_log_file, 'rb'))
  create_route(app_name,app_dir)
  host = app_name + '.94.23.211.122.nip.io'
  time.sleep(4)
  bot.send_message(chat_id=update.message.chat_id, text="Congratulation! You can reach your webapp to http://" + host)

def build_docker_image(app_name,app_dir,app_log_file,bot,update):
  os.system("oc new-app " + app_dir + "  --strategy=docker --name=" + app_name)   
  bot.send_message(chat_id=update.message.chat_id, text="Creating app " + app_name)
  os.system("oc start-build " + app_name + " --from-dir=" + app_dir)
  bot.send_message(chat_id=update.message.chat_id, text="Started build for " + app_name)
 
print "Hi! I am Openshift Bot for Telegram!"

if not os.path.exists(DATA_DIR):
    print "creating data dir " + DATA_DIR
    os.makedirs(DATA_DIR)

updater = Updater(token=BOT_TOKEN)
bot = telegram.Bot(token=BOT_TOKEN)
print(bot.get_me())

dispatcher = updater.dispatcher
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level=logging.INFO)

start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

echo_handler = MessageHandler(Filters.text, echo) 
dispatcher.add_handler(echo_handler)


dispatcher.add_handler(MessageHandler(Filters.photo, photo_handler))

updater.start_polling()

