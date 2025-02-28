import discord
from discord.ext import commands, tasks
from discord.ext.commands import CommandOnCooldown
from datetime import datetime
import time
from emoji import demojize
import json
from helper.git_backup import gitpush
from discord.ext.commands.cooldowns import BucketType
from helper.sql import SQLFunctions


def is_in(word, list_to_check):
    for v in list_to_check:
        if word.lower() == v.lower():
            return v
    return False


class Statistics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.script_start = 0
        self.waiting = False
        self.time_counter = 0  # So statistics dont get saved every few seconds, and instead only every 2 mins
        self.bot_changed_to_yesterday = {}
        self.background_git_backup.start()
        self.sent_file = False
        self.current_subject = [-1, 0]
        self.conn = SQLFunctions.connect()

    def heartbeat(self):
        return self.background_git_backup.is_running()

    def get_task(self):
        return self.background_git_backup

    @tasks.loop(seconds=10)
    async def background_git_backup(self):
        await self.bot.wait_until_ready()

        # Backs up all files every 2 hours
        if not self.sent_file and datetime.now().hour % 2 == 0:
            # Backs the data files up to github
            with open("./data/settings.json", "r") as f:
                settings = json.load(f)
            if settings["upload to git"]:
                sent_file = True
                output = gitpush("./data")
                user = self.bot.get_user(self.bot.owner_id)
                await user.send("Updated GIT\n"
                                f"Commit: `{output[0]}`\n"
                                f"Push: `{output[1]}`")
        if datetime.now().hour % 2 != 0:
            self.sent_file = False

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if "is not found" in str(error):
            return
        if ctx.message.author.bot:
            return
        else:
            if isinstance(error, CommandOnCooldown):
                embed = discord.Embed(description=str(error), color=0x8F0000)
                await ctx.send(embed=embed, delete_after=3)
            try:
                await ctx.message.add_reaction("<:ERROR:792154973559455774>")
            except discord.errors.NotFound:
                pass
            print(f"ERROR: {str(error)}")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        if ctx.message.author.bot:
            return
        else:
            try:
                await ctx.message.add_reaction("<:checkmark:776717335242211329>")
            except discord.errors.NotFound:
                pass

    @commands.Cog.listener()
    async def on_ready(self):
        self.script_start = time.time()

    @commands.Cog.listener()
    async def on_message(self, message):
        # only count stats in servers
        if message.guild is None:
            return
        # deletes the message if its in #newcomers
        if message.channel.id == 815881148307210260 and not message.author.bot:
            try:
                await message.delete()
                deleted_messages = SQLFunctions.get_config("deleted_messages", self.conn)
                if len(deleted_messages) == 0:
                    deleted_messages = 0
                else:
                    deleted_messages = deleted_messages[0]
                SQLFunctions.insert_or_update_config("deleted_messages", deleted_messages+1, self.conn)
            except discord.NotFound:  # message was already deleted
                pass
        SUBJECT_ID = self.get_current_subject()
        # Makes it better to work with the message
        msg = demojize(message.content)

        char_count = len(msg)
        word_count = len(msg.split(" "))
        emoji_count = msg.count(":") // 2
        spoiler_count = msg.count("||") // 2

        # File Statistics
        files_amount = 0
        file_sizes = 0
        images_amt = 0
        for f in message.attachments:
            file_sizes += f.size
            if f.height is not None and f.height > 0:
                images_amt += 1

        SQLFunctions.update_statistics(message.author,
                                       SUBJECT_ID,
                                       conn=self.conn,
                                       messages_sent=1,
                                       characters_sent=char_count,
                                       words_sent=word_count,
                                       spoilers_sent=spoiler_count,
                                       emojis_sent=emoji_count,
                                       files_sent=files_amount,
                                       file_size_sent=file_sizes,
                                       images_sent=images_amt)

    def get_current_subject(self, semester=2) -> int:
        """
        Minor cache system to only make a subject query if it's a new minute
        Returns the current subject ID
        """
        minute = datetime.now().minute
        if self.current_subject[0] != minute:
            subject_id = SQLFunctions.get_current_subject_id(semester, conn=self.conn)
            self.current_subject = [minute, subject_id]
        return self.current_subject[1]

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.guild is None:
            return
        SUBJECT_ID = self.get_current_subject()
        SQLFunctions.update_statistics(message.author, SUBJECT_ID, messages_deleted=1)

    @commands.Cog.listener()
    async def on_message_edit(self, before, message):
        # Adds the edited message to the table
        if message.guild is None:
            return

        # gets the char difference between the two messages
        b_cont = before.content
        a_cont = message.content
        before_char_count = len(b_cont)
        before_word_count = len(b_cont.split(" "))
        before_emoji_count = b_cont.count(":") // 2
        before_spoiler_count = b_cont.count("||") // 2
        after_char_count = len(a_cont)
        after_word_count = len(a_cont.split(" "))
        after_emoji_count = a_cont.count(":") // 2
        after_spoiler_count = a_cont.count("||") // 2

        SUBJECT_ID = self.get_current_subject()
        SQLFunctions.update_statistics(message.author,
                                       SUBJECT_ID,
                                       messages_edited=1,
                                       characters_sent=after_char_count - before_char_count,
                                       words_sent=after_word_count - before_word_count,
                                       emojis_sent=after_emoji_count - before_emoji_count,
                                       spoilers_sent=after_spoiler_count - before_spoiler_count)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, member):
        if reaction.message.guild is None or member.bot:
            return
        SUBJECT_ID = self.get_current_subject()
        SQLFunctions.update_statistics(member, SUBJECT_ID, reactions_added=1)
        if member.id == reaction.message.author.id:
            return
        SQLFunctions.update_statistics(reaction.message.author, SUBJECT_ID, reactions_received=1)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, member):
        if reaction.message.guild is None or member.bot:
            return
        SUBJECT_ID = self.get_current_subject()
        SQLFunctions.update_statistics(member, SUBJECT_ID, reactions_removed=1)
        if member.id == reaction.message.author.id:
            return
        SQLFunctions.update_statistics(reaction.message.author, SUBJECT_ID, reactions_taken_away=1)

    async def create_embed(self, member: discord.Member, statistic_columns) -> discord.Embed:
        """
        Creates an embed for a user's single statistics
        """
        embed = discord.Embed(title=f"Statistics for {str(member)}")
        for key in statistic_columns.keys():
            column = statistic_columns[key]
            size = len(column)
            rank = 0
            val = None
            for row in column:
                rank += 1
                if row[0].DiscordUserID == member.id and row[0].DiscordGuildID == member.guild.id:
                    val = row[1]
                    break
            if val is not None and key == "FileSizeSent":
                val = round(val / 1000000.0, 2)
                val = f"{val} MB"
            if val is None:  # if the user's stats are out of the limit
                embed.add_field(name=key, value=f"Can't show rank >{size}")
            else:
                embed.add_field(name=key, value=f"{val} *({rank}.)*\n")
        return embed

    async def get_top_users(self, statistic_columns=None, single_statistic=None, single_statistic_name=None, name="Top User Statistics"):
        """
        Gets the top results in either a given dictionary of multiple columns or a single column.
        In a single column the column name must be given, underwise an AssertionError is thrown.
        """
        if single_statistic is None:
            single_statistic = []
        if statistic_columns is None:
            statistic_columns = {}
            assert single_statistic_name is not None
            statistic_columns[single_statistic_name] = single_statistic

        embed = discord.Embed(title=name)
        for key in statistic_columns.keys():
            column = statistic_columns[key]
            lb_msg = ""
            for i, row in enumerate(column):
                member: SQLFunctions.DiscordMember = row[0]
                value = row[1]
                if key == "FileSentSize":
                    value = round(value / 1000000.0, 2)
                    value = f"{value} MB"
                lb_msg += f"**{i + 1}.** <@{member.DiscordUserID}> *({value})*\n"
            embed.add_field(name=key, value=lb_msg)
        return embed

    @commands.cooldown(4, 10, BucketType.user)
    @commands.guild_only()
    @commands.group(aliases=["stats"], usage="statistics [user]", invoke_without_command=True)
    async def statistics(self, ctx, user=None):
        """
        Used to call the statistics page of a user or of the server.
        The user parameter can be another user or "top" to get the top three users \
        of each category.
        """
        if ctx.invoked_subcommand is None:
            statistic_columns = {
                "MessagesSent": [],
                "MessagesDeleted": [],
                "MessagesEdited": [],
                "CharactersSent": [],
                "WordsSent": [],
                "SpoilersSent": [],
                "EmojisSent": [],
                "FilesSent": [],
                "FileSizeSent": [],
                "ImagesSent": [],
                "ReactionsAdded": [],
                "ReactionsRemoved": [],
                "ReactionsReceived": [],
                "ReactionsTakenAway": []
            }

            for key in statistic_columns.keys():
                statistic_columns[key] = SQLFunctions.get_statistic_rows(key, 500, self.conn)
            if user is None:
                embed = await self.create_embed(ctx.message.author, statistic_columns)
                await ctx.send(embed=embed)
            else:
                try:
                    memberconverter = discord.ext.commands.MemberConverter()
                    member = await memberconverter.convert(ctx, user)
                except discord.ext.commands.errors.BadArgument:
                    await ctx.send("Invalid user. Mention the user for this to work.")
                    raise discord.ext.commands.errors.BadArgument
                embed = await self.create_embed(member, statistic_columns)
                await ctx.send(embed=embed)

    @commands.guild_only()
    @statistics.command()
    async def top(self, ctx):
        statistic_columns = {
            "MessagesSent": [],
            "MessagesDeleted": [],
            "MessagesEdited": [],
            "CharactersSent": [],
            "WordsSent": [],
            "SpoilersSent": [],
            "EmojisSent": [],
            "FilesSent": [],
            "FileSizeSent": [],
            "ImagesSent": [],
            "ReactionsAdded": [],
            "ReactionsRemoved": [],
            "ReactionsReceived": [],
            "ReactionsTakenAway": []
        }
        for key in statistic_columns.keys():
            statistic_columns[key] = SQLFunctions.get_statistic_rows(key, 3, self.conn)
        embed = await self.get_top_users(statistic_columns)
        await ctx.send(embed=embed)

    @commands.guild_only()
    @statistics.command(aliases=["messages", "messagessent"], usage="MessagesSent [amount shown]")
    async def MessagesSent(self, ctx, mx=10):
        """
        See MessagesSent Stats. `amount shown` is the amount of users that \
        should be displayed in the leaderboard. Min: 1, Max: 20.
        """
        if mx < 0:
            mx = 1
        elif mx > 20:
            mx = 20
        column = SQLFunctions.get_statistic_rows("MessagesSent", mx, self.conn)
        embed = await self.get_top_users(single_statistic=column, single_statistic_name="Messages Sent")
        await ctx.send(embed=embed)

    @commands.guild_only()
    @statistics.command(aliases=["messagesdeleted"], usage="MessagesDeleted [amount shown]")
    async def MessagesDeleted(self, ctx, mx=10):
        """
        See MessagesDeleted Stats. `amount shown` is the amount of users that \
        should be displayed in the leaderboard. Min: 1, Max: 20.
        """
        if mx < 0:
            mx = 1
        elif mx > 20:
            mx = 20
        column = SQLFunctions.get_statistic_rows("MessagesDeleted", mx, self.conn)
        embed = await self.get_top_users(single_statistic=column, single_statistic_name="Messages Deleted")
        await ctx.send(embed=embed)

    @commands.guild_only()
    @statistics.command(aliases=["messagesedited"], usage="MessagesEdited [amount shown]")
    async def MessagesEdited(self, ctx, mx=10):
        """
        See MessagesEdited Stats. `amount shown` is the amount of users that \
        should be displayed in the leaderboard. Min: 1, Max: 20.
        """
        if mx < 0:
            mx = 1
        elif mx > 20:
            mx = 20
        column = SQLFunctions.get_statistic_rows("MessagesEdited", mx, self.conn)
        embed = await self.get_top_users(single_statistic=column, single_statistic_name="Messages Edited")
        await ctx.send(embed=embed)

    @commands.guild_only()
    @statistics.command(aliases=["characterssent", "characters", "chars"], usage="CharactersSent [amount shown]")
    async def CharactersSent(self, ctx, mx=10):
        """
        See CharactersSent Stats. `amount shown` is the amount of users that \
        should be displayed in the leaderboard. Min: 1, Max: 20.
        """
        if mx < 0:
            mx = 1
        elif mx > 20:
            mx = 20
        column = SQLFunctions.get_statistic_rows("CharactersSent", mx, self.conn)
        embed = await self.get_top_users(single_statistic=column, single_statistic_name="Characters Sent")
        await ctx.send(embed=embed)

    @commands.guild_only()
    @statistics.command(aliases=["wordssent", "words"], usage="WordsSent [amount shown]")
    async def WordsSent(self, ctx, mx=10):
        """
        See WordsSent Stats. `amount shown` is the amount of users that \
        should be displayed in the leaderboard. Min: 1, Max: 20.
        """
        if mx < 0:
            mx = 1
        elif mx > 20:
            mx = 20
        column = SQLFunctions.get_statistic_rows("WordsSent", mx, self.conn)
        embed = await self.get_top_users(single_statistic=column, single_statistic_name="Words Sent")
        await ctx.send(embed=embed)

    @commands.guild_only()
    @statistics.command(aliases=["spoilerssent", "spoilers"], usage="SpoilersSent [amount shown]")
    async def SpoilersSent(self, ctx, mx=10):
        """
        See SpoilersSent Stats. `amount shown` is the amount of users that \
        should be displayed in the leaderboard. Min: 1, Max: 20.
        """
        if mx < 0:
            mx = 1
        elif mx > 20:
            mx = 20
        column = SQLFunctions.get_statistic_rows("SpoilersSent", mx, self.conn)
        embed = await self.get_top_users(single_statistic=column, single_statistic_name="Spoilers Sent")
        await ctx.send(embed=embed)

    @commands.guild_only()
    @statistics.command(aliases=["emojissent", "emoji", "emojis"], usage="EmojisSent [amount shown]")
    async def EmojisSent(self, ctx, mx=10):
        """
        See EmojisSent Stats. `amount shown` is the amount of users that \
        should be displayed in the leaderboard. Min: 1, Max: 20.
        """
        if mx < 0:
            mx = 1
        elif mx > 20:
            mx = 20
        column = SQLFunctions.get_statistic_rows("EmojisSent", mx, self.conn)
        embed = await self.get_top_users(single_statistic=column, single_statistic_name="Emojis Sent")
        await ctx.send(embed=embed)

    @commands.guild_only()
    @statistics.command(aliases=["filessent", "files", "file"], usage="FilesSent [amount shown]")
    async def FilesSent(self, ctx, mx=10):
        """
        See FilesSent Stats. `amount shown` is the amount of users that \
        should be displayed in the leaderboard. Min: 1, Max: 20.
        """
        if mx < 0:
            mx = 1
        elif mx > 20:
            mx = 20
        column = SQLFunctions.get_statistic_rows("FilesSent", mx, self.conn)
        embed = await self.get_top_users(single_statistic=column, single_statistic_name="Files Sent")
        await ctx.send(embed=embed)

    @commands.guild_only()
    @statistics.command(aliases=["filesizesent", "filesize", "size"], usage="FileSizeSent [amount shown]")
    async def FileSizeSent(self, ctx, mx=10):
        """
        See FileSizeSent Stats. `amount shown` is the amount of users that \
        should be displayed in the leaderboard. Min: 1, Max: 20.
        """
        if mx < 0:
            mx = 1
        elif mx > 20:
            mx = 20
        column = SQLFunctions.get_statistic_rows("FileSizeSent", mx, self.conn)
        embed = await self.get_top_users(single_statistic=column, single_statistic_name="Total File Size Sent")
        await ctx.send(embed=embed)

    @commands.guild_only()
    @statistics.command(aliases=["imagessent", "img", "image", "images"], usage="ImagesSent [amount shown]")
    async def ImagesSent(self, ctx, mx=10):
        """
        See ImagesSent Stats. `amount shown` is the amount of users that \
        should be displayed in the leaderboard. Min: 1, Max: 20.
        """
        if mx < 0:
            mx = 1
        elif mx > 20:
            mx = 20
        column = SQLFunctions.get_statistic_rows("ImagesSent", mx, self.conn)
        embed = await self.get_top_users(single_statistic=column, single_statistic_name="Images Sent")
        await ctx.send(embed=embed)

    @commands.guild_only()
    @statistics.command(aliases=["reactionsadded", "reactions", "reaction"], usage="ReactionsAdded [amount shown]")
    async def ReactionsAdded(self, ctx, mx=10):
        """
        See ReactionsAdded Stats. `amount shown` is the amount of users that \
        should be displayed in the leaderboard. Min: 1, Max: 20.
        """
        if mx < 0:
            mx = 1
        elif mx > 20:
            mx = 20
        column = SQLFunctions.get_statistic_rows("ReactionsAdded", mx, self.conn)
        embed = await self.get_top_users(single_statistic=column, single_statistic_name="Reactions Added")
        await ctx.send(embed=embed)

    @commands.guild_only()
    @statistics.command(aliases=["reactionsremoved"], usage="ReactionsRemoved [amount shown]")
    async def ReactionsRemoved(self, ctx, mx=10):
        """
        See ReactionsRemoved Stats. `amount shown` is the amount of users that \
        should be displayed in the leaderboard. Min: 1, Max: 20.
        """
        if mx < 0:
            mx = 1
        elif mx > 20:
            mx = 20
        column = SQLFunctions.get_statistic_rows("ReactionsRemoved", mx, self.conn)
        embed = await self.get_top_users(single_statistic=column, single_statistic_name="Reactions Removed")
        await ctx.send(embed=embed)

    @commands.guild_only()
    @statistics.command(aliases=["reactionsreceived"], usage="ReactionsReceived [amount shown]")
    async def ReactionsReceived(self, ctx, mx=10):
        """
        See only ReactionsReceived Stats. `amount shown` is the amount of users that \
        should be displayed in the leaderboard. Min: 1, Max: 20.
        """
        if mx < 0:
            mx = 1
        elif mx > 20:
            mx = 20
        column = SQLFunctions.get_statistic_rows("ReactionsReceived", mx, self.conn)
        embed = await self.get_top_users(single_statistic=column, single_statistic_name="Reactions Received")
        await ctx.send(embed=embed)

    @commands.guild_only()
    @statistics.command(aliases=["reactionstakenaway"], usage="ReactionsTakenAway [amount shown]")
    async def ReactionsTakenAway(self, ctx, mx=10):
        """
        See only ReactionsTakenAway Stats. `amount shown` is the amount of users that \
        should be displayed in the leaderboard. Min: 1, Max: 20.
        """
        if mx < 0:
            mx = 1
        elif mx > 20:
            mx = 20
        column = SQLFunctions.get_statistic_rows("ReactionsTakenAway", mx, self.conn)
        embed = await self.get_top_users(single_statistic=column, single_statistic_name="Reactions Taken Away")
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Statistics(bot))
