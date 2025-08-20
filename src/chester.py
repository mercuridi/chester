"""Main code for Chester"""
# first-party imports
import logging
import os

# third-party imports
import dotenv
import discord
from discord.ext import commands


# global variables
DISCORD_API_VERSION = 10
DISCORD_API_ENDPOINT_BASE_URL = f"https://discord.com/api/v{DISCORD_API_VERSION}"
LOGGING_DESTINATION = "logs/chester.log"

# set up discord intents
INTENTS = discord.Intents.default()
INTENTS.message_content = True

# set up bot prefix
BOT = commands.Bot(command_prefix='>', intents=INTENTS)

# bot commands
@BOT.command()
async def ping(ctx):
    """basic example of creating a command and a reply"""
    await ctx.send('pong')

def main():
    """driver code for chester"""

    # load env
    dotenv.load_dotenv()

    # make handlers
    filehandler = logging.FileHandler(
        filename=LOGGING_DESTINATION,
        mode="w",
        encoding="utf8",
    )
    streamhandler = logging.StreamHandler()

    # set up logging with handlers
    logging.basicConfig(
        handlers=[
            filehandler, streamhandler
        ],
        level=logging.DEBUG
    )

    # run the bot
    logging.info("Starting discord bot")
    BOT.run(os.environ.get("DISCORD_BOT_TOKEN"))
    logging.info("Script finish")

if __name__ == "__main__":
    # call main function on direct run for script
    main()