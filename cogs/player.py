import discord
from discord.ext import commands
from datetime import datetime
import psutil
import time
import random
from sympy.solvers import solve
from sympy import symbols, simplify
import multiprocessing
from helper.log import log
import string
import hashlib
import json
from pytz import timezone


class Player(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.script_start = 0
        self.clap_counter = 0
        self.time = 0
        self.covid_guesses = {}
        self.confirmed_cases = 0
        self.confirm_msg = None  # Confirmed message
        with open("./data/covid_guesses.json") as f:
            self.covid_points = json.load(f)

    @commands.Cog.listener()
    async def on_ready(self):
        self.script_start = time.time()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if time.time() - self.time > 10:
            self.clap_counter = 0
        if "👏" in message.content:
            await message.add_reaction("👏")
            self.clap_counter += 1
            self.time = time.time()
            if self.clap_counter >= 3:
                self.clap_counter = 0
                await message.channel.send("👏\n👏\n👏")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, member):
        if member.bot:
            return
        if member.guild_permissions.kick_members:
            if str(reaction) == "<:checkmark:769279808244809798>" and reaction.message.guild.id == 747752542741725244:
                await self.confirm_msg.delete()
                self.confirm_msg = None
                start_msg = f"**CASES HAVE BEEN CONFIRMED:** `{self.confirmed_cases}`\n" \
                            f"Sending point distribution...\n" \
                            f"---------------------\n"
                points_list = await self.point_distribute(reaction.message.guild)
                msg = "\n".join(points_list)
                await reaction.message.channel.send(f"{start_msg}**__POINTS GOTTEN FOR TODAY'S GUESS:__**\n{msg}")
            elif str(reaction) == "<:xmark:769279807916998728>":
                await self.confirm_msg.delete()
                self.confirm_msg = None
                self.confirmed_cases = 0
                await reaction.message.channel.send("Confirmed cases amount was stated as being wrong and was therefore deleted.")

    async def point_distribute(self, guild):
        # if the server key is not in the file yet
        if str(guild.id) not in self.covid_points:
            self.covid_points[str(guild.id)] = {}

        sorted_keys = {}
        points = []
        log(f"Starting COVID points distribution", "COVID")
        for u in self.covid_guesses:
            user_id = u
            difference = abs(self.confirmed_cases - self.covid_guesses[user_id])
            points_gotten = float(self.confirmed_cases - difference) / self.confirmed_cases * 1000
            if points_gotten < 0:
                points_gotten = 0
            sorted_keys[user_id] = points_gotten

            # if the user has no key entry in the covid_guesses.json yet
            if user_id not in self.covid_points[str(guild.id)]:
                self.covid_points[str(guild.id)][user_id] = round(points_gotten, 1)
            else:
                self.covid_points[str(guild.id)][user_id] += round(points_gotten, 1)

        sorted_keys = sorted(sorted_keys.items(), key=lambda x: x[1], reverse=True)
        rank = 1
        for key in sorted_keys:
            user_id = key[0]
            member = guild.get_member(int(user_id))
            display_name = member.display_name.replace("*", "").replace("_", "").replace("~", "").replace("\\", "").replace("`", "").replace("||", "").replace("@", "")
            msg = f"**{rank}:** {display_name} guessed {self.covid_guesses[user_id]}: {int(round(key[1]))} points"
            points.append(msg)
            rank += 1

        with open("./data/covid_guesses.json", "w") as f:
            json.dump(self.covid_points, f, indent=2)
        log("Saved covid_guesses.json", "COVID")

        self.covid_guesses = {}
        self.confirmed_cases = 0
        return points

    @commands.command(aliases=["g"])
    async def guess(self, ctx, number=None, confirmed_number=None):
        total_points = 0
        if str(ctx.message.guild.id) in self.covid_points and str(ctx.message.author.id) in self.covid_points[str(ctx.message.guild.id)]:
            total_points = self.covid_points[str(ctx.message.guild.id)][str(ctx.message.author.id)]
        # Send last guess from user
        # Should only be possible in the morning
        hour = int(datetime.now(timezone("Europe/Zurich")).strftime("%H"))
        if 0 < hour < 12 or number is not None and number.lower() == "confirm":
            if number is None:
                if str(ctx.message.author.id) in self.covid_guesses:
                    await ctx.send(f"{ctx.message.author.mention}, "
                                   f"your final guess is `{self.covid_guesses[str(ctx.message.author.id)]}`.\n"
                                   f"Your total points: {int(round(total_points))}")
                else:
                    await ctx.send(f"{ctx.message.author.mention}, you don't have a guess yet.\n"
                                   f"Your total points: {int(round(total_points))}")
            else:
                try:
                    if number.lower() == "confirm" and ctx.author.guild_permissions.kick_members:
                        # if the number of cases gets confirmed

                        if confirmed_number is None:
                            raise ValueError
                        self.confirmed_cases = int(confirmed_number)
                        if self.confirm_msg is not None:
                            # Deletes the previous confirm message if there are multiple
                            await self.confirm_msg.delete()
                            self.confirm_msg = None
                        self.confirm_msg = await ctx.send(f"Confirmed cases: {self.confirmed_cases}\nA mod or higher, press the <:checkmark:769279808244809798> to verify.")
                        await self.confirm_msg.add_reaction("<:checkmark:769279808244809798>")
                        await self.confirm_msg.add_reaction("<:xmark:769279807916998728>")
                    else:
                        number = int(number)
                        if number < 0:
                            raise ValueError
                        if number > 1000000:
                            number = 1000000
                        self.covid_guesses[str(ctx.message.author.id)] = number
                        await ctx.send(f"{ctx.message.author.mention}, your new guess is: `{number}`")
                except ValueError:
                    await ctx.send(f"{ctx.message.author.mention}, no proper positive integer given.")
                    raise discord.ext.commands.errors.BadArgument
        else:
            await ctx.send("You can only guess in the morning till 12:00.\n"
                           f"Your total points: {int(round(total_points))}")

    @commands.command(aliases=["uptime", "source", "code"])
    async def info(self, ctx):
        """
        Get some info about the bot
        """
        async with ctx.typing():
            b_time = time_up(time.time() - self.script_start)  # uptime of the script
            s_time = time_up(seconds_elapsed())  # uptime of the pc
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory()

            cont = f"**Instance uptime: **`{b_time}`\n" \
                   f"**Computer uptime: **`{s_time}`\n" \
                   f"**CPU: **`{round(cpu)}%` | **RAM: **`{round(ram.percent)}%`\n"\
                   f"**Discord.py Rewrite Version:** `{discord.__version__}`\n" \
                   f"**Bot source code:** [Click here for source code](https://github.com/markbeep/Lecturfier)"
            embed = discord.Embed(title="Bot Information:", description=cont, color=0xD7D7D7,
                                  timestamp=datetime.now())
            embed.set_footer(text=f"Called by {ctx.author.display_name}")
            embed.set_thumbnail(url=self.bot.user.avatar_url)
            embed.set_author(name=self.bot.user.display_name, icon_url=self.bot.user.avatar_url)
        await ctx.send(embed=embed)

    @commands.command()
    async def calc(self, ctx):
        if "iq" in ctx.message.content.lower():
            await ctx.send(f"Stop asking for your fucking IQ. Nobody cares about your {random.randint(1,10)} IQ")
            return
        await ctx.send(f"{ctx.message.author.mention}: I guess {random.randrange(-1000000, 1000000)}. Could be wrong tho...")

    def simp(self, eq):
        eq = simplify(eq)
        return eq

    @commands.command()
    async def solve(self, ctx, *num1):
        """
        Solves an equation and then sends it. Deprecated, as it causes the bot to crash
        :param ctx: message object
        :param num1: equation to solve
        :return: None
        """
        if not await self.bot.is_owner(ctx.author):
            raise discord.ext.commands.errors.NotOwner
        try:
            inp = " ".join(num1)
            cont = inp.replace(" ", "").replace("^", "**")

            sides = cont.split("=")
            if "=" in cont:
                fixed = f"{sides[0]} - ({sides[1]})"
            else:
                fixed = sides[0]

            p = multiprocessing.Process(target=self.simp, name="simplify", args=(fixed,))
            p.start()

            p.join(5)

            if p.is_alive():
                await ctx.send("Solving took more than 2 seconds and was therefore stopped. Probably because of a too big of an input.")
                # Terminate simp
                p.terminate()
                p.join()
                return
            log(fixed, "SOLVE")

            variables = []
            for element in list(fixed):
                if element.isalpha() and symbols(element) not in variables:
                    variables.append(symbols(element))

            solution = ""
            for v in variables:
                log(v, "SOLVE")
                solved = solve(fixed, v)
                log(solved, "SOLVE")
                if len(solved) > 0:
                    solution += f"{v} = {{{str(solved).replace('[', '').replace(']', '')}}}\n"

            if len(solution) > 3000:
                await ctx.send("Lol there are too many numbers in that solution to display here on discord...")
                return
            embed = discord.Embed(title=f"Solved {str(fixed).replace('**', '^')}", description=solution.replace('**', '^'))
            await ctx.send(embed=embed)
        except ValueError:
            await ctx.send("Wrong syntax. You probably forgot some multiplication signs (*) or you're trying too hard to break the bot.")
        except IndexError:
            await ctx.send("No answer. Whoops")
        except NotImplementedError:
            await ctx.send("You've bested me. Don't have an algorithm to solve that yet.")

    @commands.command(aliases=["pong", "ding"])
    async def ping(self, ctx):
        """
        Check the ping of the bot
        """
        title = "Pong!"
        if "pong" in ctx.message.content.lower():
            title = "Ping!"
        if "pong" in ctx.message.content.lower() and "ping" in ctx.message.content.lower():
            title = "Ding?"
        if "ding" in ctx.message.content.lower():
            title = "*slap!*"

        embed = discord.Embed(
            title=f"{title} 🏓",
            description=f"🌐 Ping: \n"
                        f"❤ HEARTBEAT:")

        start = time.perf_counter()
        ping = await ctx.send(embed=embed)
        end = time.perf_counter()
        embed = discord.Embed(
            title=f"{title} 🏓",
            description=f"🌐 Ping: `{round((end-start)*1000)}` ms\n"
                        f"❤ HEARTBEAT: `{round(self.bot.latency * 1000)}` ms")
        await ping.edit(embed=embed)

    @commands.command()
    async def cipher(self, ctx, amount=None, *msg):
        printable = list(string.printable)
        printable = printable[0:-5]
        if len(msg) == 0:
            await ctx.send("No message specified.")
            raise discord.ext.commands.errors.BadArgument
        try:
            amount = int(amount)
        except ValueError:
            await ctx.send("Amount is not an int.")
            raise discord.ext.commands.errors.BadArgument
        msg = " ".join(msg)
        encoded_msg = ""
        amount = amount % len(printable)
        for letter in msg:
            index = printable.index(letter) + amount
            if index >= len(printable) - 1:
                index = index - (len(printable))
            encoded_msg += printable[index]

        await ctx.send(f"```{encoded_msg}```")

    @commands.command()
    async def hash(self, ctx, algo=None, *msg):
        if algo is None:
            await ctx.send("No Algorithm given. `$hash <OPENSSL algo> <msg>`")
            raise discord.ext.commands.errors.BadArgument
        try:
            joined_msg = " ".join(msg)
            msg = joined_msg.encode('UTF-8')
            h = hashlib.new(algo)
            h.update(msg)
            output = h.hexdigest()
            embed = discord.Embed(
                title=f"**Hashed message using {algo.lower()}**",
                colour=0x000000
            )
            embed.add_field(name="Input:", value=f"{joined_msg}", inline=False)
            embed.add_field(name="Output:", value=f"`{output}`", inline=False)
            await ctx.send(embed=embed)
        except ValueError:
            await ctx.send("Invalid hash type. Most OpenSSL algorithms are supported. Usage: `$hash <hash algo> <msg>`")
            raise discord.ext.commands.errors.BadArgument


def setup(bot):
    bot.add_cog(Player(bot))


def time_up(t):
    if t <= 60:
        return f"{int(t)} seconds"
    elif 3600 > t > 60:
        minutes = t // 60
        seconds = t % 60
        return f"{int(minutes)} minutes and {int(seconds)} seconds"
    elif t >= 3600:
        hours = t // 3600  # Seconds divided by 3600 gives amount of hours
        minutes = (t % 3600) // 60  # The remaining seconds are looked at to see how many minutes they make up
        seconds = (t % 3600) - minutes*60  # Amount of minutes remaining minus the seconds the minutes "take up"
        if hours >= 24:
            days = hours // 24
            hours = hours % 24
            return f"{int(days)} days, {int(hours)} hours, {int(minutes)} minutes and {int(seconds)} seconds"
        else:
            return f"{int(hours)} hours, {int(minutes)} minutes and {int(seconds)} seconds"


def seconds_elapsed():
    now = datetime.now()
    current_timestamp = time.mktime(now.timetuple())
    return current_timestamp - psutil.boot_time()
