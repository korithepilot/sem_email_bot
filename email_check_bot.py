import os
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import discord
from discord.ext import tasks
from dotenv import load_dotenv

from datetime import date, timedelta

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
TOKEN = ""
GUILD = ""
CHANNEL = ""

async def process_subject(subject):
  label_message = False
  
  if("vesztettem" in subject.lower()):
    await channel_handle.send("vesztettem")

    label_message = True
    
  if("hálóreg" in subject.lower()):
    react = await channel_handle.send("###FELADAT###\nHálóregisztrációval kapcsolatos hír került a KSZK-s levlistára:\n🔳 Hálóregisztrációk újítva")
    #await react.add_reaction("🔳")
    await react.add_reaction("✅")
    #await react.add_reaction("❌")
    label_message = True
  
  return label_message

def gmail_setup():
  creds = None
  
  if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          "gmail_key.json", SCOPES
      )
      creds = flow.run_local_server(port=0)
      
    with open("token.json", "w") as token:
      token.write(creds.to_json())
  return creds

async def process_unread_message(service, unread_message, botlabel_id):
  # Get message
  msg = service.users().messages().get(userId='me', id=unread_message['id'], format="full").execute()
  
  # Get Subject of message
  payload = msg["payload"]
  header = payload.get("headers")
  for x in header:
      if x['name'] == 'Subject':
          sub = x['value']
          
  label_message = await process_subject(sub)
  if(label_message == True):
    service.users().messages().modify(userId="me", id=unread_message['id'], body={'addLabelIds': [botlabel_id]}).execute()
    
def check_botlabel(service):
    results = service.users().labels().list(userId="me").execute()
    labels = results.get("labels", [])
    
    for label in labels:
        if(label['name'] == 'BOTREAD'):
            return(True, label['id'])
            
    return (False, '')
    
def get_botlabel_id(service):
    (has_botlabel, botlabel_id) = check_botlabel(service)
    
    if(has_botlabel == False):
        service.users().labels().create(userId="me", body={'name':'BOTREAD'}).execute()
        (_, botlabel_id) = check_botlabel(service)
        
    return botlabel_id
  
async def check_mail(creds):  
  try:
    service = build("gmail", "v1", credentials=creds)
    
    botlabel_id = get_botlabel_id(service)
    
    yesterday = date.today() - timedelta(1)
    query = "in:inbox after:{0} -label:BOTREAD".format(yesterday.strftime('%Y/%m/%d'))
    results = service.users().messages().list(userId="me", q=query).execute()
    unread_messages = results.get("messages", [])

    if not unread_messages:
      return
  
    for unread_message in unread_messages:
      await process_unread_message(service, unread_message, botlabel_id)

  except HttpError as error:
    print(f"An error occurred: {error}")
    
def start_discord_bot(creds):
  client = discord.Client(intents=discord.Intents.default())
    
  @tasks.loop(seconds=10)
  async def mail_task():
    await client.wait_until_ready()
    
    global channel_handle
    channel_handle = client.get_channel(int(CHANNEL))
    
    await check_mail(creds)
  
  @client.event
  async def on_ready():
    print(f'{client.user} has connected to Discord!')
    mail_task.start()
    
  @client.event
  async def on_raw_reaction_add(payload):
    channel = client.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    
    if message.author.id != int(BOT_ID):
      return
    
    if payload.user_id == int(BOT_ID):
      return
    
    if str(payload.emoji) == "✅":
      await message.edit(content=message.content.replace("🔳", "✅"))
    
    if str(payload.emoji) == "🔳":
      await message.edit(content=message.content.replace("✅", "🔳"))
          
    if str(payload.emoji) == "❌":
      await message.delete()
    
  client.run(TOKEN)
  
def env_setup():
  load_dotenv()
  
  global TOKEN
  TOKEN = os.getenv('DISCORD_TOKEN')
  
  global GUILD
  GUILD = os.getenv('DISCORD_GUILD')
  
  global CHANNEL
  CHANNEL = os.getenv('DISCORD_CHANNEL')
  
  global BOT_ID
  BOT_ID = os.getenv('BOT_ID')

def main():
  env_setup()
  creds = gmail_setup()
  start_discord_bot(creds)

if __name__ == "__main__":
  main()