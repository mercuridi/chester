"""Music handling cog for Chester"""
# src/musiccog.py

# first-party imports
import logging
import os
import asyncio
import glob
import json
from typing import Any

# third-party imports
import pandas as pd
import yt_dlp
import discord
from discord.ext import commands
from tabulate import tabulate

class MusicCog(commands.Cog):
    """Class to handle all audio/music functionality in Chester"""
    def __init__(self, bot: commands.Bot) -> None:
        logging.info("Instantiating music cog")
        self.bot: commands.Bot = bot
        self.loop_enabled: bool = False
        self.metadata_columns: list[str] = [
            "id",
            "title",
            "channel",
            "upload_date",
            "duration_string"
        ]
        self.load_library()        # load the library of downloaded songs
        self.max_column_width = 30 # set the max column width for library printing
        # TODO: should these dictionaries track the channel instead of the user?
        self.break_mode: dict[str, bool] = {} # dict tracking break mode for each user
        self.saved_track: dict[str, str] = {} # dict tracking the saved track for each user
        self.ydl_options: dict[str, Any] = {
            'format': 'm4a/bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }],
            "outtmpl": 'library/audio/%(id)s',
            'noplaylist': True, # disables getting playlist
            'print_to_file': { # enables json output for metadata
                'video': [
                    # defines the json output format and destination
                    ('%(.{id,title,channel,upload_date,duration_string})#j',
                    'library/metadata/%(id)s.json')
                ]
            }
        }
        self.breakpath = "library/config/break.json"
        logging.info("Finished instantiation of music cog")


    def truncate(self, s: str) -> str:
        """Trims the given string s to the set max column width"""
        if not isinstance(s, str):
            raise TypeError(f"Given argument {s} is not a string")
        logging.info("Truncating string %s", s)
        return s if len(s) <= self.max_column_width else s[:self.max_column_width-1] + "…"


    def load_library(self) -> None:
        """Loads the metadata of the local library, checking for mismatches"""
        logging.info("Loading local music library metadata")
        df = pd.DataFrame(columns=self.metadata_columns)
        metadata_files = glob.glob('library/metadata/*.json')
        logging.info("Found metadata files: %s", metadata_files)
        metadata = []
        for file_path in metadata_files:
            logging.info("Handling metadata file %s", file_path)
            track_id = file_path.split("/")[2].split(".")[0]
            if not os.path.isfile(self.get_track_filepath(track_id)):
                logging.error("Metadata file %s has no matching audio file", file_path)
                raise FileNotFoundError(f"Expected to find a matching audio file for metadata file {file_path}")

            with open(file_path, 'r', encoding="utf-8") as file_handle:
                logging.info("Opened file %s", file_path)
                file_data = file_handle.read()
                metadata_dict = json.loads(file_data)
                logging.info("Data loaded: %s", metadata_dict)
                file_data_list = []
                for key in self.metadata_columns:
                    file_data_list.append(metadata_dict[key])
                logging.info("Flattened to list: %s", file_data_list)
                metadata.append(file_data_list)

        logging.info("Metadata list: %s", metadata)
        df = pd.DataFrame(metadata, columns=self.metadata_columns)
        logging.info("Metadata dataframe:\n%s", df)
        self.library = df
        logging.info("Set self.library to above metadata dataframe")


    def get_title_from_id(self, given_id: str) -> str:
        """Gets the track title for a given metadata ID"""
        logging.info("Getting title for id %s", given_id)
        found = self.library.loc[self.library['id'] == given_id]["title"]
        if len(found) == 0:
            raise ValueError("The requested ID was not found in the library")
        found_title = found.iloc[0]
        logging.info("Found title for id %s: %s", given_id, found_title)
        return found_title


    def download_m4a(self, url: str):
        """Downloads the m4a track for a given youtube URL"""
        logging.info("Downloading m4a track for URL %s", url)
        with yt_dlp.YoutubeDL(self.ydl_options) as ydl:
            logging.info("Extracting info without download")
            info = ydl.extract_info(url, download=False)
            logging.info("Processing info & triggering download")
            ydl.process_info(info) # triggers download
            logging.info("Getting track ID of downloaded content")
            return ydl.prepare_filename(info).split("/")[2]

        logging.error("File download failed for URL %s", url)
        raise RuntimeError(f"The file download failed for URL {url}")


    def get_track_filepath(self, track_id: str) -> str:
        """Returns the audio filepath for a given ID"""
        return f"library/audio/{track_id}.m4a"


    @commands.command(name="registerbreak")
    async def cmd_registerbreak(self, ctx: commands.Context, *args: tuple):
        """Command to register a break track per user"""
        logging.info("Registering break track")
        given_id = "".join(args[0])
        logging.info("Given break id: %s", given_id)
        if given_id not in self.library["id"].values:
            await ctx.send(f"{ctx.author.mention} The ID `{given_id}` does not correspond to a known track.")
            return
        track_title = self.get_title_from_id(given_id)
        logging.info("Given track ID %s corresponds to track titled %s", given_id, track_title)

        
        if os.path.exists(self.breakpath):
            logging.info("Break file record exists, opening")
            with open(self.breakpath, "r", encoding="utf-8") as read_handle:
                read_data = read_handle.read()
                break_dict = json.loads(read_data)
        else:
            logging.info("Break record does not exist, starting new")
            break_dict = {}
        logging.info("Break record contents: %s", break_dict)


        logging.info(
            "Adding track %s with id %s as user %s's break music (user id: %s)",
            track_title,
            given_id,
            ctx.author.display_name,
            ctx.author.id
        )

        break_dict[str(ctx.author.id)] = given_id
        logging.info("Writing out updated break record")
        with open(self.breakpath, "w+", encoding="utf-8") as write_handle:
            json.dump(break_dict, write_handle, ensure_ascii=False)

        await ctx.send(f"Registered {ctx.author.mention}'s break music as `{track_title}`")
        logging.info("Added track to break record")

    @commands.command(name="library")
    async def cmd_library(self, ctx: commands.Context):
        """Command to display the available library"""
        logging.info("Displaying available tracks in library")
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
        logging.info("Sent message for library display")


    @commands.command(name="loop")
    async def cmd_loop(self, ctx: commands.Context):
        """Global loop toggle"""
        logging.info("Toggling loop switch; current value %s", self.loop_enabled)
        self.loop_enabled = not self.loop_enabled
        status = "enabled" if self.loop_enabled else "disabled"
        logging.info("Toggle value to %s", self.loop_enabled)
        await ctx.send(f"{ctx.author.mention} Loop {status}")


    @commands.command(name="download")
    async def cmd_download(self, ctx: commands.Context, *args):
        """Downloads a track given a URL in the argument"""
        logging.info(ctx.message.content)
        link = args[0]
        logging.info(link)
        await ctx.send(f"{ctx.message.author.mention} Attempting to download track at URL `{link}`.")
        try:
            track_id = self.download_m4a(link)
        except RuntimeError as e:
            await ctx.send("An internal error occurred while downloading the file. Please contact the developer.")
            raise RuntimeError(e) from e
        self.load_library()
        await ctx.send(f"{ctx.message.author.mention} Successfully downloaded track `{self.get_title_from_id(track_id)}` and reloaded the library.")
        logging.info("Downloaded track %s from URL %s", self.get_title_from_id(track_id), link)

    @commands.command(name="hardreset")
    async def cmd_hardreset(self, ctx: commands.Context):
        """Command to reset all data files"""
        logging.info("Performing hard reset on database")
        await ctx.send(f"{ctx.message.author.mention} Attempting to hard reset library...")
        library_files = glob.glob('library/audio/*.m4a')
        metadata_files = glob.glob('library/metadata/*.json')
        config_files = glob.glob('library/config/*.json')
        all_files = library_files + metadata_files + config_files
        for file_path in all_files:
            try:
                logging.info("Removing file at %s", file_path)
                os.remove(file_path)
            except RuntimeError as e:
                logging.error("Failed to delete %s. Reason: %s", file_path, e)
        await ctx.send(f"{ctx.message.author.mention} Hard reset complete")
        logging.info("Hard reset complete")


    @commands.command(name="stop")
    async def cmd_stop(self, ctx: commands.Context):
        """Stops active playback"""
        logging.info("Stopping playback")
        voice = ctx.voice_client
        if voice and voice.is_connected():
            await voice.disconnect()
            await ctx.send(f"{ctx.message.author.mention} Left the channel.")
            logging.info("Disconnected from voice")
        else:
            await ctx.send(f"{ctx.message.author.mention} There is no active track.")
            logging.info("There is no channel to disconnect from.")
        logging.info("Stopped playback")


    @commands.command(name="play")
    async def cmd_play(self, ctx: commands.Context, *args):
        """Plays a track given an ID"""
        # 1. Join or move to the user's voice channel
        logging.info("Playing track")
        try:
            channel = ctx.author.voice.channel
        except AttributeError:
            return await ctx.send(f"{ctx.author.mention} You are not in a voice channel.")
        logging.info("Target user channel found")

        voice = ctx.voice_client
        if voice and voice.is_connected():
            await voice.move_to(channel)
        else:
            voice = await channel.connect()
        logging.info("Joined target user voice channel")

        # 2. Build track path & stash for resume
        track_id = args[0]
        track_file = self.get_track_filepath(track_id)
        track_title = self.get_title_from_id(track_id)
        user_id = str(ctx.author.id)
        self.saved_track[user_id] = track_file
        logging.info("Saved track ID for resume")

        # 3. Start playback
        logging.info("Playing the track %s", track_title)
        self._play_with_loop(voice, track_file)

        await ctx.send(f"Now playing `{track_title}`.")
    
    def _play_with_loop(self, voice: discord.VoiceClient, track_file: str):
        def _after_play(error):
            if self.loop_enabled:
                # replay the same file
                logging.info("Loop enabled. Replaying track %s.", track_file)
                voice.play(discord.FFmpegPCMAudio(track_file), after=_after_play)
            else:
                # schedule a disconnect on the bot's loop when loop is turned off
                # TODO not intended behaviour
                logging.info("Loop disabled, ending playback of current track")
                coro = voice.disconnect()
                asyncio.run_coroutine_threadsafe(coro, self.bot.loop)

        # start playback
        source = discord.FFmpegPCMAudio(track_file)
        voice.play(source, after=_after_play)

    @commands.command(name="break")
    async def cmd_break(self, ctx: commands.Context):
        """Command to quickly switch to registered break music"""
        user_id = str(ctx.author.id)
        logging.info("Switching to break music for user %s", ctx.author.display_name)

        # 1. load break.json
        logging.info("Loading break configuration file")
        with open("library/config/break.json", "r", encoding="utf-8") as f:
            break_dict = json.load(f)
        track_id = break_dict.get(user_id)
        if not track_id:
            await ctx.send(f"{ctx.author.mention} Please register a break track to enable this command.")
            return

        logging.info("Getting voice client for target user channel")
        voice = ctx.voice_client or await ctx.author.voice.channel.connect()

        # 2. toggle
        if self.break_mode.get(user_id):
            # → turn OFF break mode
            logging.info("Disabling break mode for user %s", user_id)
            self.break_mode[user_id] = False
            voice.stop()  # stops the looping break track

            original_file = self.saved_track.get(user_id)
            if original_file:
                logging.info("Found original track %s", original_file)
                source = discord.FFmpegPCMAudio(original_file)
                voice.play(source, after=lambda e: None)
                await ctx.send(f"Resuming previous track `{self.get_title_from_id(original_file)}`")
            else:
                await ctx.send("No original track to resume.")
        else:
            # → turn ON break mode
            # pause or stop whatever's playing
            if voice.is_playing():
                logging.info("Pausing active track")
                voice.pause()
            
            logging.info("Enabling break mode for user %s", user_id)
            self.break_mode[user_id] = True

            break_file = self.get_track_filepath(track_id)
            source = discord.FFmpegPCMAudio(break_file)

            # define a recursive after-callback to loop
            def _loop_break(error):
                if self.break_mode.get(user_id):
                    logging.info("Looping break music after finished playback")
                    voice.play(discord.FFmpegPCMAudio(break_file), after=_loop_break)

            voice.play(source, after=_loop_break)
            await ctx.send(f"Playing pre-set break music: `{self.get_title_from_id(track_id)}`")


async def setup(bot):
    logging.info("Adding cog for music")
    await bot.add_cog(MusicCog(bot))
    logging.info("Music cog added")

