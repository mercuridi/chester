"""Main code for Chester"""
# first-party imports
import logging
import os
import asyncio
import glob

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

# set up global toggles
# TODO find a better way to handle this
LOOP = False


def hook(d):
    if d["status"] == "downloading":
        logging.info("%s %s", d['filename'], d['_percent_str'])
    elif d["status"] == "finished":
        logging.info("%s %s", d['filename'], d['_percent_str'])


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
    await ctx.send(f"{ctx.message.author.mention} Attempting to download track at URL `{link}`.")
    try:
        name = download_m4a(link)
    except RuntimeError as e:
        await ctx.send("An internal error occurred while downloading the file. Please contact the developer.")
        raise RuntimeError(e) from e
    await ctx.send(f"{ctx.message.author.mention} Successfully downloaded track `{name}`.")
    logging.info(name)

@BOT.command()
async def resethard(ctx):
    await ctx.send(f"{ctx.message.author.mention} Attempting to hard reset library...")
    library_files = glob.glob('library/*')
    metadata_files = glob.glob('metadata/*')
    all_files = library_files + metadata_files
    for file_path in all_files:
        try:
            os.remove(file_path)
        except Exception as e:
            logging.error("Failed to delete %s. Reason: %s", file_path, e)
    await ctx.send(f"{ctx.message.author.mention} Hard reset complete")


def download_m4a(url):
    ydl_opts = {
        'format': 'm4a/bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }],
        "outtmpl": 'library/%(id)s',
        'noplaylist': True, # disables getting playlist
        'progress_hooks': [hook], # adds the progress hook
        'print_to_file': {
            'video': [
                # defines the json output format and destination
                ('%(.{id,display_id,title,channel,upload_date,duration_string})#j',
                'metadata/%(id)s.json')
            ]
        }
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        ydl.process_info(info) # triggers download
        return ydl.prepare_filename(info)

    logging.error("File download failed")
    raise RuntimeError("A file download failed")

@BOT.command()
async def loop(ctx):
    global LOOP
    if LOOP is True:
        LOOP = False
        await ctx.send(f"{ctx.message.author.mention} Loop disabled")
    else:
        LOOP = True
        await ctx.send(f"{ctx.message.author.mention} Loop enabled")


@BOT.command()
async def stop(ctx):
    voice = discord.utils.get(BOT.voice_clients, guild=ctx.guild)
    if voice and voice.is_connected():
        await voice.disconnect()
        await ctx.send(f"{ctx.message.author.mention} Left the channel.")
    else:
        await ctx.send(f"{ctx.message.author.mention} There is no active track.")


@BOT.command()
async def play(ctx, *args):
    try:
        channel = ctx.message.author.voice.channel
    except AttributeError as e:
        logging.warning(e)
        channel = None

    if not channel:
        await ctx.send(f"{ctx.message.author.mention} You are not connected to a voice channel.")
        return

    voice = discord.utils.get(BOT.voice_clients, guild=ctx.guild)
    if voice and voice.is_connected():
        await voice.move_to(channel)
    else:
        voice = await channel.connect()

    track_name = ' '.join(args)
    source = discord.FFmpegPCMAudio(f"library/{track_name}.m4a")
    if LOOP is True:
        while LOOP:
            player = voice.play(source)
            while not player.is_done():
                await asyncio.sleep(1)
    else:
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
