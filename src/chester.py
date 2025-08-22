"""Main code for Chester"""
# first-party imports
import logging
import os
import asyncio

# third-party imports
import dotenv
import discord
import yt_dlp
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


@BOT.command()
async def download(ctx):
    logging.info(ctx.message.content)
    link = ctx.message.content.split()[1]
    logging.info(link)
    name = download_m4a(link)
    await ctx.send(f"Downloaded track `{name}`.")
    logging.info(name)

def download_m4a(url):
    ydl_opts = {
        'format': 'm4a/bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }],
        "outtmpl": 'library/%(uploader)s_%(title)s.%(ext)s'
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info).split("/")[1]
        ydl.process_info(info)  # starts the download

    return file_path.split(".")[0]

@BOT.command()
async def play(ctx):
    channel = ctx.message.author.voice.channel
    if not channel:
        await ctx.send("You are not connected to a voice channel")
        return
    voice = discord.utils.get(BOT.voice_clients, guild=ctx.guild)
    if voice and voice.is_connected():
        await voice.move_to(channel)
    else:
        voice = await channel.connect()
    source = discord.FFmpegPCMAudio('library/Jack Wall_Vigil.m4a')
    player = voice.play(source)
    while not player.is_done():
        await asyncio.sleep(1)
    # disconnect after the player has finished
    player.stop()
    await voice.disconnect()



def start_bot():
    # run the bot
    logging.info("Starting discord bot")
    BOT.run(os.environ.get("DISCORD_BOT_TOKEN"))
    logging.info("Script finish")

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

    start_bot()
    #logging.info(download_m4a('https://youtu.be/SPa8bPqQfmo'))

if __name__ == "__main__":
    # call main function on direct run for script
    main()
