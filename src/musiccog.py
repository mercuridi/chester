"""Music handling cog for Chester"""
# src/musiccog.py

# first-party imports
import logging
import os
import asyncio
import glob
import json

# third-party imports
import pandas as pd
import yt_dlp
import discord
from discord.ext import commands
from tabulate import tabulate

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop_enabled = False
        self.metadata_columns = [
            "id",
            "title",
            "channel",
            "upload_date",
            "duration_string"
        ]
        self.load_library()
        logging.info(self.library)
        self.max_column_width = 30
        self.break_mode: dict[str, bool] = {}  
        self.saved_track: dict[str, str] = {}

    def truncate(self, s):
        return s if len(s) <= self.max_column_width else s[:self.max_column_width] + "…"


    def load_library(self):
        df = pd.DataFrame(columns=self.metadata_columns)
        metadata_files = glob.glob('library/metadata/*.json')
        metadata = []
        for file_path in metadata_files:
            logging.info(file_path)
            file_id = file_path.split("/")[2].split(".")[0]
            if not os.path.isfile(f"library/audio/{file_id}.m4a"):
                raise FileNotFoundError(f"Expected to find a matching audio file for metadata file {file_id}")

            with open(file_path, 'r', encoding="utf-8") as file_handle:
                file_data = file_handle.read()
                metadata_dict = json.loads(file_data)
                file_data_list = []
                for key in self.metadata_columns:
                    file_data_list.append(metadata_dict[key])
                metadata.append(file_data_list)

        df = pd.DataFrame(metadata, columns=self.metadata_columns)
        self.library = df


    def get_title_from_id(self, given_id):
        found = self.library.loc[self.library['id'] == given_id]["title"]
        if len(found) == 0:
            raise RuntimeError("The requested ID was not found in the library")
        return found.iloc[0]


    def hook(self, d):
        if d["status"] == "downloading":
            logging.info("%s %s", d['filename'], d['_percent_str'])
        elif d["status"] == "finished":
            logging.info("%s %s", d['filename'], d['_percent_str'])


    def download_m4a(self, url):
        ydl_opts = {
            'format': 'm4a/bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }],
            "outtmpl": 'library/audio/%(id)s',
            'noplaylist': True, # disables getting playlist
            'progress_hooks': [self.hook], # adds the progress hook
            'print_to_file': { # enables json output for metadata
                'video': [
                    # defines the json output format and destination
                    ('%(.{id,title,channel,upload_date,duration_string})#j',
                    'library/metadata/%(id)s.json')
                ]
            }
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            ydl.process_info(info) # triggers download
            return ydl.prepare_filename(info)

        logging.error("File download failed")
        raise RuntimeError("A file download failed")

    def get_track_filepath(self, track_id):
        return f"library/audio/{track_id}.m4a"

    @commands.command(name="registerbreak")
    async def cmd_registerbreak(self, ctx, *args):
        given_id = args[0]
        if given_id not in self.library["id"].values:
            await ctx.send(f"{ctx.author.mention} The ID `{given_id}` does not correspond to a known track.")
            return

        breakpath = "library/config/break.json"
        if os.path.exists(breakpath):
            with open(breakpath, "r", encoding="utf-8") as read_handle:
                read_data = read_handle.read()
                break_dict = json.loads(read_data)
        else:
            break_dict = {}

        break_dict[str(ctx.author.id)] = given_id

        with open(breakpath, "w+", encoding="utf-8") as write_handle:
            json.dump(break_dict, write_handle, ensure_ascii=False)
        await ctx.send(f"Registered {ctx.author.mention}'s break music as `{self.get_title_from_id(given_id)}`")


    @commands.command(name="library")
    async def cmd_library(self, ctx):
        library_display = self.library.copy()
        library_display["duration"] = library_display["duration_string"]
        library_display = library_display.drop(
            labels=[
                "upload_date",
                "duration_string",
                "channel",
                "duration"
            ], axis="columns"
        )
        library_display["title"] = library_display["title"].apply(self.truncate)
        table = tabulate(library_display, headers="keys",
                        tablefmt="rounded_outline",
                        showindex=False)

        msg = (
            f"{ctx.author.mention} Available library:\n"
            f"```{table}```"
        )
        await ctx.send(msg)


    @commands.command(name="loop")
    async def cmd_loop(self, ctx):
        self.loop_enabled = not self.loop_enabled
        status = "enabled" if self.loop_enabled else "disabled"
        await ctx.send(f"{ctx.author.mention} Loop {status}")


    @commands.command(name="download")
    async def cmd_download(self, ctx, *args):
        logging.info(ctx.message.content)
        link = args[0]
        logging.info(link)
        await ctx.send(f"{ctx.message.author.mention} Attempting to download track at URL `{link}`.")
        try:
            name = self.download_m4a(link)
        except RuntimeError as e:
            await ctx.send("An internal error occurred while downloading the file. Please contact the developer.")
            raise RuntimeError(e) from e
        self.load_library()
        await ctx.send(f"{ctx.message.author.mention} Successfully downloaded track `{name}` and reloaded the library.")


    @commands.command(name="hardreset")
    async def cmd_hardreset(self, ctx):
        await ctx.send(f"{ctx.message.author.mention} Attempting to hard reset library...")
        library_files = glob.glob('library/audio/*.m4a')
        metadata_files = glob.glob('library/metadata/*.json')
        all_files = library_files + metadata_files
        for file_path in all_files:
            try:
                os.remove(file_path)
            except RuntimeError as e:
                logging.error("Failed to delete %s. Reason: %s", file_path, e)
        await ctx.send(f"{ctx.message.author.mention} Hard reset complete")


    @commands.command(name="stop")
    async def cmd_stop(self, ctx):
        voice = ctx.voice_client
        if voice and voice.is_connected():
            await voice.disconnect()
            await ctx.send(f"{ctx.message.author.mention} Left the channel.")
        else:
            await ctx.send(f"{ctx.message.author.mention} There is no active track.")


    @commands.command(name="play")
    async def cmd_play(self, ctx, *args):
        # 1. Join or move to the user's voice channel
        try:
            channel = ctx.author.voice.channel
        except AttributeError:
            return await ctx.send(f"{ctx.author.mention} You're not in a voice channel!")

        voice = ctx.voice_client
        if voice and voice.is_connected():
            await voice.move_to(channel)
        else:
            voice = await channel.connect()

        # 2. Build track path & stash for resume
        track_id = args[0]
        track_file = self.get_track_filepath(track_id)
        user_id = str(ctx.author.id)
        self.saved_track[user_id] = track_file

        # 3. Enable looping and kick off the after-callback
        self._play_with_loop(voice, track_file)

        await ctx.send(f"▶️ Now playing *{self.get_title_from_id(track_id)}* on loop. Use your break/stop command to toggle.")
    
    def _play_with_loop(self, voice: discord.VoiceClient, track_file: str):
        def _after_play(error):
            if self.loop_enabled:
                # replay the same file
                voice.play(discord.FFmpegPCMAudio(track_file), after=_after_play)
            else:
                # schedule a disconnect on the bot's loop when loop is turned off
                coro = voice.disconnect()
                asyncio.run_coroutine_threadsafe(coro, self.bot.loop)

        # start playback
        source = discord.FFmpegPCMAudio(track_file)
        voice.play(source, after=_after_play)

    @commands.command(name="break")
    async def cmd_break(self, ctx):
        user_id = str(ctx.author.id)

        # 1. load break.json
        with open("library/config/break.json", "r", encoding="utf-8") as f:
            break_dict = json.load(f)
        track_id = break_dict.get(user_id)
        if not track_id:
            return await ctx.send(f"{ctx.author.mention} you haven't registered a break track yet!")

        voice = ctx.voice_client or await ctx.author.voice.channel.connect()

        # 2. toggle
        if self.break_mode.get(user_id):
            # → turn OFF break mode
            self.break_mode[user_id] = False
            voice.stop()  # stops the looping break track

            original_file = self.saved_track.get(user_id)
            if original_file:
                source = discord.FFmpegPCMAudio(original_file)
                voice.play(source, after=lambda e: None)
                await ctx.send("🔄 Resuming previous track.")
            else:
                await ctx.send("No original track to resume.")
        else:
            # → turn ON break mode
            # pause or stop whatever's playing
            if voice.is_playing():
                voice.pause()
            self.break_mode[user_id] = True

            break_file = self.get_track_filepath(track_id)
            source = discord.FFmpegPCMAudio(break_file)

            # define a recursive after-callback to loop
            def _loop_break(error):
                if self.break_mode.get(user_id):
                    voice.play(discord.FFmpegPCMAudio(break_file), after=_loop_break)

            voice.play(source, after=_loop_break)
            await ctx.send("🛑⏸️ Playing your break music on loop!")


async def setup(bot):
    await bot.add_cog(MusicCog(bot))
