"""Main code for Chester"""
# src/chester.py

# first-party imports
import logging
import os
import asyncio
from typing import Any

# third-party imports
import dotenv
import discord
from discord.ext import commands

# global variables
DISCORD_API_VERSION = 10
DISCORD_API_ENDPOINT_BASE_URL = f"https://discord.com/api/v{DISCORD_API_VERSION}"
LOGGING_DESTINATION = "logs/chester.log"


class Chester(commands.Bot):
    """Wrapper for commands.Bot"""
    def __init__(self, **kwargs: dict[str, Any]):
        super().__init__(**kwargs)


async def main():
    """Driver function to set up important config for Chester"""
    # set up logging
    filehandler = logging.FileHandler(LOGGING_DESTINATION, mode="w", encoding="utf8")
    streamhandler = logging.StreamHandler()
    logging.basicConfig(handlers=[filehandler, streamhandler], level=logging.INFO)

    # create bot
    intents = discord.Intents.default()
    intents.message_content = True
    bot = Chester(command_prefix=">", intents=intents)

    # load cogs
    await bot.load_extension("musiccog")
    logging.info("registered commands: %s", [c.name for c in bot.commands])

    # start the bot
    token = os.environ["DISCORD_BOT_TOKEN"]
    await bot.start(token)

if __name__ == "__main__":
    dotenv.load_dotenv()
    asyncio.run(main())
