"""Music handling cog for Chester"""
# src/musiccog.py

# first-party imports
import logging
import os
import asyncio
import glob

# third-party imports
import discord
import yt_dlp
from discord.ext import commands

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop_enabled = False
    def hook(self, d):
        if d["status"] == "downloading":
            logging.info("%s %s", d['filename'], d['_percent_str'])
        elif d["status"] == "finished":
            logging.info("%s %s", d['filename'], d['_percent_str'])

    @commands.command(name="loop")
    async def cmd_loop(self, ctx):
        # self.loop_enabled lives on your Bot instance
        self.loop_enabled = not self.loop_enabled
        status = "enabled" if self.loop_enabled else "disabled"
        await ctx.send(f"{ctx.author.mention} Loop {status}")

    @commands.command(name="download")
    async def cmd_download(self, ctx):
        logging.info(ctx.message.content)
        link = ctx.message.content.split()[1]
        logging.info(link)
        await ctx.send(f"{ctx.message.author.mention} Attempting to download track at URL `{link}`.")
        try:
            name = self.download_m4a(link)
        except RuntimeError as e:
            await ctx.send("An internal error occurred while downloading the file. Please contact the developer.")
            raise RuntimeError(e) from e
        await ctx.send(f"{ctx.message.author.mention} Successfully downloaded track `{name}`.")
        logging.info(name)

    @commands.command(name="hardreset")
    async def cmd_hardreset(self, ctx):
        await ctx.send(f"{ctx.message.author.mention} Attempting to hard reset library...")
        library_files = glob.glob('library/*')
        metadata_files = glob.glob('metadata/*')
        all_files = library_files + metadata_files
        for file_path in all_files:
            try:
                os.remove(file_path)
            except RuntimeError as e:
                logging.error("Failed to delete %s. Reason: %s", file_path, e)
        await ctx.send(f"{ctx.message.author.mention} Hard reset complete")


    def download_m4a(self, url):
        ydl_opts = {
            'format': 'm4a/bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }],
            "outtmpl": 'library/%(id)s',
            'noplaylist': True, # disables getting playlist
            'progress_hooks': [self.hook], # adds the progress hook
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


    @commands.command(name="stop")
    async def cmd_stop(self, ctx):
        voice = discord.utils.get(self.voice_clients, guild=ctx.guild)
        if voice and voice.is_connected():
            await voice.disconnect()
            await ctx.send(f"{ctx.message.author.mention} Left the channel.")
        else:
            await ctx.send(f"{ctx.message.author.mention} There is no active track.")


    @commands.command(name="play")
    async def cmd_play(self, ctx, *args):
        try:
            channel = ctx.message.author.voice.channel
        except AttributeError as e:
            logging.warning(e)
            channel = None

        if not channel:
            await ctx.send(f"{ctx.message.author.mention} You are not connected to a voice channel.")
            return

        voice = ctx.voice_client
        if voice and voice.is_connected():
            await voice.move_to(channel)
        else:
            voice = await channel.connect()

        track_name = ' '.join(args)
        track_file = f"library/{track_name}.m4a"
        # keep looping until someone flips the flag off
        while True:
            source = discord.FFmpegPCMAudio(track_file)
            ctx.voice_client.play(source)
            # wait for this play to finish
            while ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
                await asyncio.sleep(0.5)
            # break out if looping is disabled
            if not self.loop_enabled:
                break

        # disconnect after the player has finished
        await ctx.voice_client.disconnect()

async def setup(bot):
    await bot.add_cog(MusicCog(bot))
