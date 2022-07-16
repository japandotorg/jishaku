# -*- coding: utf-8 -*-

"""
jishaku.features.python
~~~~~~~~~~~~~~~~~~~~~~~~

The jishaku Python evaluation/execution commands.

:copyright: (c) 2021 Devon (Gorialis) R
:license: MIT, see LICENSE for more details.

"""

import io
import sys
import typing
import inspect
import asyncio

import discord
from redbot.core import commands
from redbot.core.utils.chat_formatting import box

from jishaku.codeblocks import codeblock_converter
from jishaku.exception_handling import ReplResponseReactor
from jishaku.features.baseclass import Feature
from jishaku.flags import Flags
from jishaku.functools import AsyncSender
from jishaku.paginators import PaginatorInterface, WrappedPaginator, use_file_check
from jishaku.repl import AsyncCodeExecutor, Scope, all_inspections, create_tree, disassemble, get_var_dict_from_ctx


class PythonFeature(Feature):
    """
    Feature containing the Python-related commands
    """

    def __init__(self, *args: typing.Any, **kwargs: typing.Any):
        super().__init__(*args, **kwargs)
        self._scope = Scope()
        self.retain = Flags.RETAIN
        self.last_result: typing.Any = None
        self.repl_sessions = set()

    @property
    def scope(self):
        """
        Gets a scope for use in REPL.

        If retention is on, this is the internal stored scope,
        otherwise it is always a new Scope.
        """

        if self.retain:
            return self._scope
        return Scope()

    @Feature.Command(parent="jsk", name="retain")
    async def jsk_retain(self, ctx: commands.Context, *, toggle: bool = None):
        """
        Turn variable retention for REPL on or off.

        Provide no argument for current status.
        """

        if toggle is None:
            if self.retain:
                return await ctx.send("Variable retention is set to ON.")

            return await ctx.send("Variable retention is set to OFF.")

        if toggle:
            if self.retain:
                return await ctx.send("Variable retention is already set to ON.")

            self.retain = True
            self._scope = Scope()
            return await ctx.send("Variable retention is ON. Future REPL sessions will retain their scope.")

        if not self.retain:
            return await ctx.send("Variable retention is already set to OFF.")

        self.retain = False
        return await ctx.send("Variable retention is OFF. Future REPL sessions will dispose their scope when done.")

    async def jsk_python_result_handling(self, ctx: commands.Context, result):  # pylint: disable=too-many-return-statements
        """
        Determines what is done with a result when it comes out of jsk py.
        This allows you to override how this is done without having to rewrite the command itself.
        What you return is what gets stored in the temporary _ variable.
        """

        if isinstance(result, discord.Message):
            return await ctx.send(f"<Message <{result.jump_url}>>")

        if isinstance(result, discord.File):
            return await ctx.send(file=result)

        if isinstance(result, discord.Embed):
            return await ctx.send(embed=result)

        if isinstance(result, PaginatorInterface):
            return await result.send_to(ctx)

        if not isinstance(result, str):
            # repr all non-strings
            result = repr(result)

        # Eventually the below handling should probably be put somewhere else
        if len(result) <= 2000:
            if result.strip() == '':
                result = "\u200b"

            return await ctx.send(result.replace(self.bot.http.token, "[token omitted]"))

        if use_file_check(ctx, len(result)):  # File "full content" preview limit
            # Discord's desktop and web client now supports an interactive file content
            #  display for files encoded in UTF-8.
            # Since this avoids escape issues and is more intuitive than pagination for
            #  long results, it will now be prioritized over PaginatorInterface if the
            #  resultant content is below the filesize threshold
            return await ctx.send(file=discord.File(
                filename="output.py",
                fp=io.BytesIO(result.encode('utf-8'))
            ))

        # inconsistency here, results get wrapped in codeblocks when they are too large
        #  but don't if they're not. probably not that bad, but noting for later review
        paginator = WrappedPaginator(prefix='```py', suffix='```', max_size=1985)

        paginator.add_line(result)

        interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
        return await interface.send_to(ctx)
    
    def jsk_python_get_convertables(self, ctx: commands.Context) -> typing.Tuple[typing.Dict[str, typing.Any], typing.Dict[str, str]]:
        """
        Gets the arg dict and convertables for this scope.
        
        The arg dict contains the 'locals' to be propagated into the REPL scope.
        The convertables are string->string conversions to be attempted if the code fails to parse.
        """
        
        arg_dict = get_var_dict_from_ctx(ctx, Flags.SCOPE_PREFIX)
        arg_dict["_"] = self.last_result
        convertables: typing.Dict[str, str] = {}
        
        for index, user in enumerate(ctx.message.mentions):
            arg_dict[f"__user_mention_{index}"] = user
            convertables[user.mention] = f"__user_mention_{index}"

        for index, channel in enumerate(ctx.message.channel_mentions):
            arg_dict[f"__channel_mention_{index}"] = channel
            convertables[channel.mention] = f"__channel_mention_{index}"

        for index, role in enumerate(ctx.message.role_mentions):
            arg_dict[f"__role_mention_{index}"] = role
            convertables[role.mention] = f"__role_mention_{index}"

        return arg_dict, convertables

    @Feature.Command(parent="jsk", name="py", aliases=["python", "eval"])
    async def jsk_python(self, ctx: commands.Context, *, argument: codeblock_converter):
        """
        Direct evaluation of Python code.
        """

        arg_dict = get_var_dict_from_ctx(ctx, Flags.SCOPE_PREFIX)
        arg_dict["_"] = self.last_result

        scope = self.scope

        try:
            async with ReplResponseReactor(ctx.message):
                with self.submit(ctx):
                    executor = AsyncCodeExecutor(argument.content, scope, arg_dict=arg_dict)
                    async for send, result in AsyncSender(executor):
                        if result is None:
                            continue

                        self.last_result = result

                        send(await self.jsk_python_result_handling(ctx, result))

        finally:
            scope.clear_intersection(arg_dict)

    @Feature.Command(parent="jsk", name="py_inspect", aliases=["pyi", "python_inspect", "pythoninspect"])
    async def jsk_python_inspect(self, ctx: commands.Context, *, argument: codeblock_converter):  # pylint: disable=too-many-locals
        """
        Evaluation of Python code with inspect information.
        """

        arg_dict = get_var_dict_from_ctx(ctx, Flags.SCOPE_PREFIX)
        arg_dict["_"] = self.last_result

        scope = self.scope

        try:
            async with ReplResponseReactor(ctx.message):
                with self.submit(ctx):
                    executor = AsyncCodeExecutor(argument.content, scope, arg_dict=arg_dict)
                    async for send, result in AsyncSender(executor):
                        self.last_result = result

                        header = repr(result).replace("``", "`\u200b`").replace(self.bot.http.token, "[token omitted]")

                        if len(header) > 485:
                            header = header[0:482] + "..."

                        lines = [f"=== {header} ===", ""]

                        for name, res in all_inspections(result):
                            lines.append(f"{name:16.16} :: {res}")

                        text = "\n".join(lines)

                        if use_file_check(ctx, len(text)):  # File "full content" preview limit
                            send(await ctx.send(file=discord.File(
                                filename="inspection.prolog",
                                fp=io.BytesIO(text.encode('utf-8'))
                            )))
                        else:
                            paginator = WrappedPaginator(prefix="```prolog", max_size=1985)

                            paginator.add_line(text)

                            interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
                            send(await interface.send_to(ctx))
        finally:
            scope.clear_intersection(arg_dict)

    @Feature.Command(parent="jsk", name="dis", aliases=["disassemble"])
    async def jsk_disassemble(self, ctx: commands.Context, *, argument: codeblock_converter):
        """
        Disassemble Python code into bytecode.
        """

        arg_dict = get_var_dict_from_ctx(ctx, Flags.SCOPE_PREFIX)

        async with ReplResponseReactor(ctx.message):
            text = "\n".join(disassemble(argument.content, arg_dict=arg_dict))

            if use_file_check(ctx, len(text)):  # File "full content" preview limit
                await ctx.send(file=discord.File(
                    filename="dis.py",
                    fp=io.BytesIO(text.encode('utf-8'))
                ))
            else:
                paginator = WrappedPaginator(prefix='```py', max_size=1985)

                paginator.add_line(text)

                interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
                await interface.send_to(ctx)
                
    @Feature.Command(parent="jsk", name="ast")
    async def jsk_ast(self, ctx: commands.Context, *, argument: codeblock_converter): # type: ignore
        """
        Disassemble Python code into AST.
        """
        
        if typing.TYPE_CHECKING:
            argument: Codeblock = argument # type: ignore
            
        async with ReplResponseReactor(ctx.bot, ctx.message):
            text = create_tree(argument.content, use_ansi=Flags.use_ansi(ctx))
            
            await ctx.send(file=discord.File(
                filename="ast.ansi",
                fp=io.BytesIO(text.encode("utf-8"))
            ))
                
    @Feature.Command(parent="jsk", name="repl")
    async def jsk_repl(self, ctx: commands.Context):
        """
        Launches a Python interactive shell in the current channel.
        Messages not starting with "$" will be ignored by default.
        
        The REPL session auto exits if left idle for 10 minutes.
        
        Inspired by [R.Danny's version](https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/admin.py)
        """
        
        arg_dict, convertables = self.jsk_python_get_convertables(ctx)
        scope = self.scope
        
        if ctx.channel.id in self.repl_sessions:
            await ctx.send(
                "Already running an interactive shell in this channel. Use `exit()` or `quit()` or exit."
            )
            return
        
        banner = "Python {} on {}\n".format(sys.version.split("\n")[0], sys.platform)
        
        self.repl_sessions.add(ctx.channel.id)
        await ctx.send(box(banner, "py"))
        
        def check(m):
            return m.author.id == ctx.author.id and \
                   m.channel.id == ctx.channel.id and \
                   (True if Flags.NO_REPL_PREFX else m.content.startswith("$"))
                   
        while True:
            try:
                response = await self.bot.wait_for("message", check=check, timeout=10.0 * 60.0)
            except asyncio.TimeoutError:
                await ctx.send("Exiting...")
                self.repl_sessions.remove(ctx.channel.id)
                break
            
            argument = codeblock_converter(response.content)
            
            if argument.content in ("ext()", "quit()"):
                await ctx.send("Exiting...")
                self.repl_sessions.remove(ctx.channel.id)
                return
            elif argument.content in ("exit", "quit"):
                await ctx.send(f"Use `{argument.content}()` to exit.")
                continue
            
            arg_dict["message"] = arg_dict["msg"] = response
            
            try:
                async with ReplResponseReactor(ctx.bot, response):
                    with self.submit(ctx):
                        executor = AsyncCodeExecutor(argument.content, scope, arg_dict=arg_dict, convertables=convertables)
                        async for send, result in AsyncSender(executor):
                            if result is None:
                                continue
                            
                            self.last_result = result
                            
                            send(await self.jsk_python_result_handling(ctx, result))
                            
            finally:
                scope.clear_intersection(arg_dict)
