"""Music handling cog for Chester"""
# src/musiccog.py

# first-party imports
import logging
import os
import asyncio
import glob
import json
from typing import Any
from collections import defaultdict

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
        self.break_mode: dict[str, bool] = {} # dict tracking break mode for each channel
        self.saved_track: dict[str, str] = {} # dict tracking the saved track for each channel
        self.loop_enabled: dict[str, bool] = defaultdict(bool) # dict tracking loop mode for each channel
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
                raise FileNotFoundError(
                    f"Expected to find a matching audio file for metadata file {file_path}")

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
            raise ValueError(f"The requested ID {given_id} was not found in the library")
        found_title = found.iloc[0]
        logging.info("Found title for id %s: %s", given_id, found_title)
        return found_title


    def download_m4a(self, url: str) -> str:
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


    async def check_args_ok(self, ctx: commands.Context, args: tuple):
        """Checks if the given arguments to a command are valid"""
        if len(args) == 0:
            await ctx.send(
                f"{ctx.message.author.mention} Please provide an argument to the command")
            logging.error("No argument was provided to the command")
            return False
        return True

    async def join_caller_channel(self, ctx: commands.Context) -> discord.VoiceProtocol | None:
        """Joins the calling user's voice channel, if it exists"""
        logging.info("Joining the calling user's channel")
        channel = await self.get_caller_channel(ctx)
        if channel is None:
            return None

        voice = ctx.voice_client
        if voice and voice.is_connected():
            await voice.move_to(channel)
        else:
            voice = await channel.connect()
        logging.info("Joined target user voice channel")
        return voice

    async def get_caller_channel(self, ctx: commands.Context) -> discord.VoiceChannel | None:
        """Gets the caller's voice channel object"""
        logging.info("Getting the calling user's channel")
        try:
            channel = ctx.author.voice.channel
            logging.info("Target user channel found")
            return channel
        except AttributeError:
            await ctx.send(f"{ctx.author.mention} You are not in a voice channel.")
            logging.info("The caller is not in a voice channel")
            return None


    # registerbreak
    @commands.command(name="registerbreak")
    async def cmd_registerbreak(self, ctx: commands.Context, *args: tuple) -> None:
        """Command to register a break track per user"""
        logging.info("Registering break track")
        if not await self.check_args_ok(ctx, args):
            return
        given_id = "".join(args[0])
        logging.info("Given break id: %s", given_id)
        if given_id not in self.library["id"].values:
            await ctx.send(
                f"{ctx.author.mention} The ID `{given_id}` does not correspond to a known track.")
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

    # library
    @commands.command(name="library")
    async def cmd_library(self, ctx: commands.Context) -> None:
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

    # loop
    @commands.command(name="loop")
    async def cmd_loop(self, ctx: commands.Context) -> None:
        """Global loop toggle"""
        logging.info("Toggling loop switch")
        channel: discord.VoiceChannel = await self.get_caller_channel(ctx)
        if channel is None:
            return
        self.loop_enabled[channel.id] = not self.loop_enabled[channel.id]
        status = "enabled" if self.loop_enabled[channel.id] else "disabled"
        logging.info("Toggle value to %s", self.loop_enabled[channel.id])
        await ctx.send(f"{ctx.author.mention} Loop {status}")

    # download
    @commands.command(name="download")
    async def cmd_download(self, ctx: commands.Context, *args: tuple) -> None:
        """Downloads a track given a URL in the argument"""
        if not await self.check_args_ok(ctx, args):
            return
        logging.info(ctx.message.content)
        link = "".join(args[0])
        logging.info(link)
        await ctx.send(
            f" Attempting to download track at URL `{link}`.")
        try:
            track_id = self.download_m4a(link)
        except RuntimeError as e:
            await ctx.send(
                f"{ctx.message.author.mention} An error occurred while downloading the file.")
            raise RuntimeError(e) from e
        self.load_library()
        track_title = self.get_title_from_id(track_id)
        await ctx.send(
            "Successfully downloaded track"
            + f"`{track_title}` and reloaded the library.")
        logging.info("Downloaded track %s from URL %s", self.get_title_from_id(track_id), link)

    # hardreset
    @commands.command(name="hardreset")
    async def cmd_hardreset(self, ctx: commands.Context) -> None:
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

    # stop
    @commands.command(name="stop")
    async def cmd_stop(self, ctx: commands.Context) -> None:
        """Stops active playback"""
        logging.info("Stopping playback")
        voice = ctx.voice_client
        if voice and voice.is_connected():
            await voice.disconnect()
            await ctx.send(f"{ctx.message.author.mention} Left the channel.")
            logging.info("Disconnected from voice")
            if self.break_mode.get(voice.channel.id):
                self.break_mode.pop(voice.channel.id)
                self.saved_track.pop(voice.channel.id)
                logging.info("Cleaned up active break after stop")
            self.loop_enabled[voice.channel.id] = False
        else:
            await ctx.send(f"{ctx.message.author.mention} There is no active track.")
            logging.info("There is no channel to disconnect from.")
        logging.info("Stopped playback")

    # play
    @commands.command(name="play")
    async def cmd_play(self, ctx: commands.Context, *args: tuple) -> None:
        """Plays a track given an ID"""
        if not await self.check_args_ok(ctx, args):
            return

        # 1. Join or move to the user's voice channel
        logging.info("Playing track")
        voice: discord.VoiceProtocol = await self.join_caller_channel(ctx)
        if voice is None:
            logging.error("Caller was not in a voice channel when break command was called")
            return

        # 2. Build track path & stash for resume
        track_id   = "".join(list(args[0]))
        track_file = self.get_track_filepath(track_id)
        self.saved_track[voice.channel.id] = track_id

        def _after_play(_):
            logging.info("Checking loop flag for channel %s", voice.channel.id)
            if self.loop_enabled[voice.channel.id]:
                logging.info("Loop flag is set True, replaying track")
                voice.play(discord.FFmpegPCMAudio(track_file), after=_after_play)
            else:
                logging.info("Loop flag is set False, explicitly stopping voice playback")
                voice.stop()

        # start playback
        source = discord.FFmpegPCMAudio(track_file)
        voice.play(source, after=_after_play)
        await ctx.send(f"Now playing `{self.get_title_from_id(track_id)}`")

    # break
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
            await ctx.send(
                f"{ctx.author.mention} Please register a break track to enable this command.")
            return
        break_file = self.get_track_filepath(track_id)

        logging.info("Getting voice client for target user channel")
        voice = await self.join_caller_channel(ctx)
        if voice is None:
            logging.error("Caller was not in a voice channel when break command was called")
            return

        def _loop_break(_):
            if self.break_mode.get(voice.channel.id):
                logging.info("Track has ended but break still enabled, looping break track")
                voice.play(discord.FFmpegPCMAudio(break_file), after=_loop_break)

        # toggle on/off logic
        if self.break_mode.get(voice.channel.id):
            # → turn OFF
            self.break_mode[voice.channel.id] = False
            voice.stop()

            original_file_id = self.saved_track.get(voice.channel.id)
            if voice.channel.id in self.saved_track:
                self.saved_track.pop(voice.channel.id)
            if original_file_id:
                logging.info("Found original track %s", original_file_id)
                source = discord.FFmpegPCMAudio(self.get_track_filepath(original_file_id))
                voice.play(source, after=lambda e: None)
                await ctx.send(
                    f"Resuming previous track `{self.get_title_from_id(original_file_id)}`")
            else:
                await ctx.send(
                    f"{ctx.message.author.mention} Ending break with no original track to resume.")
        else:
            # → turn ON
            self.break_mode[voice.channel.id] = True
            if voice.is_playing():
                voice.pause()

            voice.play(discord.FFmpegPCMAudio(break_file), after=_loop_break)
            await ctx.send(f"Playing break music `{self.get_title_from_id(track_id)}`")


async def setup(bot: commands.Bot) -> None:
    """Required function for adding a cog to a bot config"""
    logging.info("Adding cog for music")
    await bot.add_cog(MusicCog(bot))
    logging.info("Music cog added")
