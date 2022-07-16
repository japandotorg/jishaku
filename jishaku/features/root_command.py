# -*- coding: utf-8 -*-

"""
jishaku.features.root_command
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The jishaku root command.

:copyright: (c) 2021 Devon (Gorialis) R
:license: MIT, see LICENSE for more details.

"""

# from importlib.metadata import packages_distributions
import math
import sys
import typing

import discord
from redbot.core import commands # type: ignore

from jishaku.features.baseclass import Feature
from jishaku.flags import Flags
from jishaku.modules import package_version
from jishaku.paginators import PaginatorInterface

try:
    import psutil
except ImportError:
    psutil = None
    
try:
    from importlib.metadata import distribution, packages_distributions
except ImportError:
    from importlib_metadata import distribution, packages_distributions  # type: ignore


def natural_size(size_in_bytes: int):
    """
    Converts a number of bytes to an appropriately-scaled unit
    E.g.:
        1024 -> 1.00 KiB
        12345678 -> 11.77 MiB
    """
    units = ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB')

    power = int(math.log(size_in_bytes, 1024))

    return f"{size_in_bytes / (1024 ** power):.2f} {units[power]}"


class RootCommand(Feature):
    """
    Feature containing the root jsk command
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.jsk.hidden = Flags.HIDE

    @Feature.Command(name="jishaku", aliases=["jsk", "mmo", "fko"],
                     invoke_without_command=True, ignore_extra=False)
    async def jsk(self, ctx: commands.Context):  # pylint: disable=too-many-branches
        """
        The Jishaku debug and diagnostic commands.

        This command on its own gives a status brief.
        All other functionality is within its subcommands.
        """
        
        distributions: typing.List[str] = [
            dist for dist in packages_distributions()['discord'] # type: ignore
            if any(
                file.parts == ('discord', '__init__.py') # type: ignore
                for file in distribution(dist).files
            )
        ]
        
        if distributions:
            dpy_version = f"{distributions[0]} v{package_version(distributions[0])}"
        else:
            dpy_version = f"unknown `{discord.__version__}`"

        summary = [
            f"Jishaku v{package_version('jishaku')} (ported for Red).",
            f"<a:mel_whitedot:930948764674449498> {dpy_version}.\n"
            f"<a:mel_whitedot:930948764674449498> Python {'.'.join(map(str, sys.version_info[:3]))} on `{sys.platform}` platform.",
            f"<a:mel_whitedot:930948764674449498> Module was loaded <t:{self.load_time.timestamp():.0f}:R>.",
            f"<a:mel_whitedot:930948764674449498> Cog was loaded <t:{self.start_time.timestamp():.0f}:R>.",
            ""
        ]

        # detect if [procinfo] feature is installed
        if psutil:
            try:
                proc = psutil.Process()

                with proc.oneshot():
                    try:
                        mem = proc.memory_full_info()
                        summary.append(f"This process is using {natural_size(mem.rss)} physical memory.\n"
                                       f"<a:mel_whitedot:930948764674449498> {natural_size(mem.vms)} virtual memory, "
                                       f"{natural_size(mem.uss)} of which unique to this process.")
                    except psutil.AccessDenied:
                        pass

                    try:
                        name = proc.name()
                        pid = proc.pid
                        thread_count = proc.num_threads()

                        summary.append(f"<a:mel_whitedot:930948764674449498> Running on PID {pid} (`{name}`) with {thread_count} thread(s).")
                    except psutil.AccessDenied:
                        pass

                    summary.append("")  # blank line
            except psutil.AccessDenied:
                summary.append(
                    "psutil is installed, but this process does not have high enough access rights "
                    "to query process information."
                )
                summary.append("")  # blank line

        cache_summary = f"{len(self.bot.guilds)} guild(s) and {len(self.bot.users)} user(s)"

        # Show shard settings to summary
        if isinstance(self.bot, discord.AutoShardedClient):
            if len(self.bot.shards) > 20:
                summary.append(
                    f"This bot is automatically sharded ({len(self.bot.shards)} shards of {self.bot.shard_count}).\n"
                    f"<a:mel_whitedot:930948764674449498> It can see {cache_summary}."
                )
            else:
                shard_ids = ', '.join(str(i) for i in self.bot.shards.keys())
                summary.append(
                    f"This bot is automatically sharded (Shards {shard_ids} of {self.bot.shard_count}).\n"
                    f"<a:mel_whitedot:930948764674449498> It can see {cache_summary}."
                )
        elif self.bot.shard_count:
            summary.append(
                f"This bot is manually sharded (Shard {self.bot.shard_id} of {self.bot.shard_count})."
                f"<a:mel_whitedot:930948764674449498> It can see {cache_summary}."
            )
        else:
            summary.append(f"This bot is not sharded\n<a:mel_whitedot:930948764674449498> It can see {cache_summary}.")

        # pylint: disable=protected-access
        if self.bot._connection.max_messages:
            message_cache = f"<a:mel_whitedot:930948764674449498> Message cache capped at {self.bot._connection.max_messages}."
        else:
            message_cache = "<a:mel_whitedot:930948764674449498> Message cache is disabled."

        if discord.version_info >= (1, 5, 0):
            
            presence_intent = f"Presence intent is {'<:melon_on:945199207495663636> enabled.' if self.bot.intents.presences else '<:melon_off:945199310100906004> disabled.'}"
            members_intent = f"Members intent is {'<:melon_on:945199207495663636> enabled.' if self.bot.intents.members else '<:melon_off:945199310100906004> disabled.'}"

            summary.append(f"{message_cache}\n<a:mel_whitedot:930948764674449498> {presence_intent}\n<a:mel_whitedot:930948764674449498> {members_intent}")
        else:
            guild_subscriptions = f"guild subscriptions are {'<:melon_on:945199207495663636> enabled.' if self.bot._connection.guild_subscriptions else '<:melon_off:945199310100906004> disabled.'}"

            summary.append(f"{message_cache}\n<a:mel_whitedot:930948764674449498> {guild_subscriptions}.")

        # pylint: enable=protected-access

        # Show websocket latency in milliseconds
        # summary.append(f"Average websocket latency: {round(self.bot.latency * 1000, 2)}ms")
        
        embed = discord.Embed(
            description="\n".join(summary), 
            color=0x2f3136,
            timestamp=ctx.message.created_at,
        )
        embed.set_footer(text=f"Average websocket latency: {round(self.bot.latency * 1000, 2)}ms")
        
        await ctx.send(embed=embed)

    # pylint: disable=no-member
    @Feature.Command(parent="jsk", name="hide")
    async def jsk_hide(self, ctx: commands.Context):
        """
        Hides Jishaku from the help command.
        """

        if self.jsk.hidden:
            return await ctx.send("Jishaku is already hidden.")

        self.jsk.hidden = True
        await ctx.send("Jishaku is now hidden.")

    @Feature.Command(parent="jsk", name="show")
    async def jsk_show(self, ctx: commands.Context):
        """
        Shows Jishaku in the help command.
        """

        if not self.jsk.hidden:
            return await ctx.send("Jishaku is already visible.")

        self.jsk.hidden = False
        await ctx.send("Jishaku is now visible.")
    # pylint: enable=no-member

    @Feature.Command(parent="jsk", name="tasks")
    async def jsk_tasks(self, ctx: commands.Context):
        """
        Shows the currently running jishaku tasks.
        """

        if not self.tasks:
            return await ctx.send("No currently running tasks.")

        paginator = commands.Paginator(max_size=1985)

        for task in self.tasks:
            paginator.add_line(f"{task.index}: `{task.ctx.command.qualified_name}`, invoked at "
                               f"{task.ctx.message.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
        return await interface.send_to(ctx)

    @Feature.Command(parent="jsk", name="cancel")
    async def jsk_cancel(self, ctx: commands.Context, *, index: typing.Union[int, str]):
        """
        Cancels a task with the given index.

        If the index passed is -1, will cancel the last task instead.
        """

        if not self.tasks:
            return await ctx.send("No tasks to cancel.")

        if index == "~":
            task_count = len(self.tasks)

            for task in self.tasks:
                task.task.cancel()

            self.tasks.clear()

            return await ctx.send(f"Cancelled {task_count} tasks.")

        if isinstance(index, str):
            raise commands.BadArgument('Literal for "index" not recognized.')

        if index == -1:
            task = self.tasks.pop()
        else:
            task = discord.utils.get(self.tasks, index=index)
            if task:
                self.tasks.remove(task)
            else:
                return await ctx.send("Unknown task.")

        task.task.cancel()
        return await ctx.send(f"Cancelled task {task.index}: `{task.ctx.command.qualified_name}`,"
                              f" invoked at {task.ctx.message.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC")
