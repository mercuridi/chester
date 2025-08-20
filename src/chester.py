"""Main code for Chester"""
# first-party imports
import logging
import requests

# third-party imports
import dotenv

# global variables
DISCORD_API_VERSION = 10
DISCORD_API_ENDPOINT_BASE_URL = f"https://discord.com/api/v{DISCORD_API_VERSION}"
LOGGING_DESTINATION = "logs/chester.log"

import discord

class MyClient(discord.Client):
    async def on_ready(self):
        print('Logged on as', self.user)

    async def on_message(self, message):
        # don't respond to ourselves
        if message.author == self.user:
            return

        if message.content == 'ping':
            await message.channel.send('pong')

intents = discord.Intents.default()
intents.message_content = True
client = MyClient(intents=intents)
client.run('token')

if __name__ == "__main__":
    dotenv.load_dotenv()
    filehandler = logging.FileHandler(
        filename=LOGGING_DESTINATION,
        mode="w",
        encoding="utf8",
    )
    streamhandler = logging.StreamHandler()
    logging.basicConfig(
        handlers=[
            filehandler, streamhandler
        ],
        level=logging.DEBUG
    )
    logging.info("Hello Logging!")
