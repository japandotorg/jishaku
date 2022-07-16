# -*- coding: utf-8 -*-

"""
jishaku.repl.repl_builtins
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Builtin functions and variables within Jishaku REPL contexts.

:copyright: (c) 2021 Devon (Gorialis) R
:license: MIT, see LICENSE for more details.

"""

import typing
import aiohttp

import discord
from redbot.core import commands


async def request(*args: typing.Any, **kwargs: typing.Any) -> typing.Union[bytes, dict]:
    """
    Performs a HTTP request against a URL, returning the response payload as bytes.
    
    The arguments to pass are the same as :func:`aiohttp.ClientSession.get`,
    with an additional ``json`` bool which indicates whether to return the result as JSON (defaults to ``True``).
    """
    json = kwargs.pop('json', True)
    
    async with aiohttp.ClientSession() as ses:
        async with ses.request(*args, **kwargs) as res:
            res.raise_for_status()
            
            if json:
                return await res.json()
            
            return await res.read()

async def http_get_bytes(*args, **kwargs) -> bytes:
    """
    Performs a HTTP GET request against a URL, returning the response payload as bytes.

    The arguments to pass are the same as :func:`aiohttp.ClientSession.get`.
    """

    async with aiohttp.ClientSession() as session:
        async with session.get(*args, **kwargs) as response:
            response.raise_for_status()

            return await response.read()


async def http_get_json(*args, **kwargs) -> dict:
    """
    Performs a HTTP GET request against a URL,
    returning the response payload as a dictionary of the response payload interpreted as JSON.

    The arguments to pass are the same as :func:`aiohttp.ClientSession.get`.
    """

    async with aiohttp.ClientSession() as session:
        async with session.get(*args, **kwargs) as response:
            response.raise_for_status()

            return await response.json()


async def http_post_bytes(*args, **kwargs) -> bytes:
    """
    Performs a HTTP POST request against a URL, returning the response payload as bytes.

    The arguments to pass are the same as :func:`aiohttp.ClientSession.post`.
    """

    async with aiohttp.ClientSession() as session:
        async with session.post(*args, **kwargs) as response:
            response.raise_for_status()

            return await response.read()


async def http_post_json(*args, **kwargs) -> dict:
    """
    Performs a HTTP POST request against a URL,
    returning the response payload as a dictionary of the response payload interpreted as JSON.

    The arguments to pass are the same as :func:`aiohttp.ClientSession.post`.
    """

    async with aiohttp.ClientSession() as session:
        async with session.post(*args, **kwargs) as response:
            response.raise_for_status()

            return await response.json()


def get_var_dict_from_ctx(ctx: commands.Context, prefix: str = '_'):
    """
    Returns the dict to be used in REPL for a given Context.
    """

    raw_var_dict = {
        'discord': discord,
        'author': ctx.author,
        'bot': ctx.bot,
        'channel': ctx.channel,
        'ctx': ctx,
        'find': discord.utils.find,
        'get': discord.utils.get,
        'guild': ctx.guild,
        'me': ctx.me,
        'http_get_bytes': http_get_bytes,
        'http_get_json': http_get_json,
        'http_post_bytes': http_post_bytes,
        'http_post_json': http_post_json,
        'request': request,
        'message': ctx.message,
        'msg': ctx.message
    }

    return {f'{prefix}{k}': v for k, v in raw_var_dict.items()}
