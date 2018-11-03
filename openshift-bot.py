#!/usr/local/bin/python
# -*- coding: utf-8 -*-
from emoji import emojize
import os
import re
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
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler

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
#BOT_START_MSG = "Please do one of these actions\n1. Take a picture\n2. Send an index.html\n"
BOT_START_MSG = ""

#Temporary attributes. Delete when usage of oc will be replaced completly by API in this bot
OC_USER = config['OPENSHIFT']['Admin_user']
OC_PASSWORD = config['OPENSHIFT']['Admin_password']

def create_route(app_name,app_dir,bot,update):
  route_request = "https://%s/apis/route.openshift.io/v1/namespaces/%s/routes" % (OC_ENDPOINT,OC_NAMESPACE)
  host = app_name + '.' + '94.23.211.122.nip.io'
  s = Template('{"kind": "Route", "spec": {"path": "/", "host": "$host", "port": {"targetPort": "8080-tcp"}, "wildcardPolicy": "None", "to": {"kind": "Service", "name": "$name", "weight": 100}}, "apiVersion": "route.openshift.io/v1", "metadata": {"labels": {"app": "$name"}, "namespace": "$namespace", "name": "$name"}}')
  r = requests.post(route_request,data=s.substitute(name=app_name,host=host,namespace=OC_NAMESPACE),verify=False,headers=headers)
  print r.text
  time.sleep(5)
  bot.send_message(chat_id=update.message.chat_id, text="Congratulation! You can reach your webapp to http://" + host + " I will delete it in 30 seconds!")

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

def pod_status(app_name):
  print "checking if " + app_name + " pod is running..."
  pod_request = "https://%s/api/v1/pods"  % (OC_ENDPOINT)
  r = requests.get(pod_request,verify=False,headers=headers)
  response = json.loads(r.text)
  for pod in response['items']:
    if pod['metadata']['name'].find(app_name) != -1 and pod['metadata']['name'].find('build') == -1:
      print "pod " + app_name + " is " + pod['status']['phase'] 
      return pod['status']['phase']

def wait_pod(app_name,bot,update):
  bot.send_message(chat_id=update.message.chat_id, text="Waiting for pod running..")
  while True:
    if pod_status(app_name) == 'Running':
      break
    else:
      time.sleep(2)

def wait_build(app_name,app_log_file,bot,update):
  build_latest_version = False
  while not build_latest_version:
    build_latest_version  = build_completed(app_name)
    time.sleep(2)
  os.system("oc logs build/" + app_name + "-" + str(build_latest_version) + "&>" + app_log_file)
  bot.send_document(chat_id=update.message.chat_id, document=open(app_log_file, 'rb'))

def random_generator(size=6, chars=string.ascii_lowercase + string.digits):
  return ''.join(random.choice(chars) for x in range(size))

def button(bot,update):
    query = update.callback_query
    if format(query.data) == '1':
      bot.send_message(query.message.chat_id,"Take a picture!" + emojize(":camera:", use_aliases=True))      
    elif format(query.data) == '2':
      bot.send_message(query.message.chat_id,"Send to an index.html file!" + emojize(":page_with_curl:", use_aliases=True))

def start(bot,update):
  #bot.send_photo(chat_id=update.message.chat_id, photo=open('openshift.png', 'rb'))
  bot.send_message(chat_id=update.message.chat_id, text=emojize(":sunglasses:", use_aliases=True) + "I'm an Openshift Telegram bot! I will build and deploy things to my cluster for you!\n" + BOT_START_MSG)
  keyboard = [
    [InlineKeyboardButton("Build and expose a pod - picture version", callback_data='1')],
    [InlineKeyboardButton("Build and expose a pod - html version", callback_data='2')],
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)
  update.message.reply_text('Please choose:', reply_markup=reply_markup)
  #bot.send_message(update.message.chat_id, "Menu", reply_markup=reply_markup)

def echo(bot, update):
  bot.send_message(chat_id=update.message.chat_id, text=BOT_START_MSG)

def create_app_dir():
  app_name = "sample-app-" + random_generator()
  app_dir = os.path.join(DATA_DIR,app_name)
  app_log_file = os.path.join(app_dir,'build.log')
  os.system("cp -r demo-image " + app_dir)
  return {"app_dir": app_dir,"app_name": app_name,"app_log_file": app_log_file}

def html_handler(bot,update):
  oc_login()
  app_hash     = create_app_dir()
  app_name     = app_hash['app_name']
  app_dir      = app_hash['app_dir']
  app_log_file = app_hash['app_log_file']
  file = bot.getFile(update.message.document)
  file.download(app_dir +'/index.html')
  build_docker_image(app_name,app_dir,app_log_file,bot,update)
  wait_build(app_name,app_log_file,bot,update)
  wait_pod(app_name,bot,update)
  create_route(app_name,app_dir,bot,update)
  oc_get_all(app_name,bot,update)
  oc_clean(app_name,bot,update)

def document_handler(bot, update):
  if re.search('\.html?$',update.message.document.file_name):
    html_handler(bot,update)
 
def photo_handler(bot,update):
  oc_login()
  app_hash     = create_app_dir()
  app_name     = app_hash['app_name']
  app_dir      = app_hash['app_dir']
  app_log_file = app_hash['app_log_file']

  file = bot.getFile(update.message.photo[-1])
  file.download(app_dir +'/from_telegram.jpg')
  build_docker_image(app_name,app_dir,app_log_file,bot,update)
  wait_build(app_name,app_log_file,bot,update)
  wait_pod(app_name,bot,update)
  create_route(app_name,app_dir,bot,update)
  oc_get_all(app_name,bot,update)
  oc_clean(app_name,bot,update)

def build_docker_image(app_name,app_dir,app_log_file,bot,update):
  bot.send_message(chat_id=update.message.chat_id, text="Building " + app_name)
  os.system("oc new-app " + app_dir + "  --strategy=docker --name=" + app_name)   
  bot.send_message(chat_id=update.message.chat_id, text="Creating app " + app_name)
  os.system("oc start-build " + app_name + " --from-dir=" + app_dir)
  bot.send_message(chat_id=update.message.chat_id, text="Started build for " + app_name)

def oc_clean(app_name,bot,update):
  clean_command = "sleep 30 && oc delete all -l app=" + app_name
  os.system(clean_command)
  time.sleep(30) 
  bot.send_message(chat_id=update.message.chat_id, text="your app " + app_name + " has been removed. Thank you for using me!" + emojize(":wink:", use_aliases=True))

def oc_login():
  login_command = "oc login -u %s -p %s -n %s" % (OC_USER,OC_PASSWORD,OC_NAMESPACE)
  print login_command
  os.system(login_command)

def oc_get_all(app_name,bot,update):
  json_file = os.path.join(DATA_DIR,app_name + ".json")
  get_all_command = "oc get all -l app=" + app_name + " -o json > " + json_file 
  os.system(get_all_command)
  bot.send_message(chat_id=update.message.chat_id, text="These are all resources you have created in my cluster")
  bot.send_document(chat_id=update.message.chat_id, document=open(json_file, 'rb'))

print "**************************************"
print "*Hi! I am Openshift Bot for Telegram!*"
print "**************************************"

oc_login()

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

start_handler = CommandHandler('help', start)
dispatcher.add_handler(start_handler)

dispatcher.add_handler(MessageHandler(Filters.text, echo))
dispatcher.add_handler(MessageHandler(Filters.photo, photo_handler))
dispatcher.add_handler(MessageHandler(Filters.document, document_handler))
updater.dispatcher.add_handler(CallbackQueryHandler(button))

updater.start_polling()
