import asyncio
import random
import sys, traceback
import logging
import json
import os
import tempfile

import discord
from discord.ext import commands

import xdice

from localutil import debug_id
import ffgame

log = logging.getLogger()

# Thread-global datastore for all this async crap
guildgames = {}

# -- Core Bot Functions

def get_prefix(bot, message):
    """A callable Prefix for our bot. This could be edited to allow per server prefixes."""

    # Notice how you can use spaces in prefixes. Try to keep them simple though.
    prefixes = [']']

    # If we are in a guild, we allow for the user to mention us or use any of the prefixes in our list.
    return commands.when_mentioned_or(*prefixes)(bot, message)

bot = commands.Bot(command_prefix=get_prefix, description='Weaver Test')

@bot.event
async def on_ready():
    """http://discordpy.readthedocs.io/en/rewrite/api.html#discord.on_ready"""

    log.info(f'\n\nLogged in as: {bot.user.name} - {bot.user.id}\nVersion: {discord.__version__}\n')

    for guild in bot.guilds:
        guildgames[guild.id] = ffgame.FFGame(guild)


    await bot.change_presence(activity=discord.CustomActivity(name='Test Bot'))
    log.info(f'\nSuccessfully logged in and booted...!\n')

@bot.event
async def on_command_error(ctx, exception):
    usage=""
    if ctx.command is not None and ctx.command.signature:
        usage= f'`{ctx.prefix}{ctx.invoked_with} {ctx.command.signature}`'
    await ctx.send(f'**{type(exception).__name__}**: {" ".join(exception.args)}{usage}'[:1999], delete_after=60*5)
 

    print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)

    traceback.print_exception(type(exception), exception, exception.__traceback__, file=sys.stderr)

# --- Admin Commands ---

@bot.command()
@commands.is_owner()
async def shutdown(ctx):
    await ctx.send("Shutting down...")
    log.info(f'Accepting shutdown request from {ctx.author} ...')
    await ctx.bot.close()

@bot.command()
async def save(ctx):
    for game in guildgames.values():
        game.save()
    await ctx.send("Saved.")    
  
# --- General Commands ---

@bot.command()
async def roll(ctx, *, expression):
    """Says when a member joined."""
    result = xdice.roll(expression)
    output = []
    for score in result.scores():
        output.append(f'{score}: {score.format(verbose=True)}')
    output = '\n'.join(output)
    await ctx.send(f'{ctx.author.mention}: {output}')


# --- Character Commands ---

@bot.command()
@commands.guild_only()
async def mychar(ctx, name: str, token: str=None,
        stat1: int=None, stat2: int=None, stat3: int=None, stat4: int=None, stat5: int=None):
    """
    Set up your personal character all in one go.

    Name: Your character's name. Please "quote multi-word" names. 
    Token: Your character's single character token for the init tracker, default to first of name.
    Air, Earth, Fire, Water: The raw 0-255 value from your character sheet, deault to zero.
    Init: Number of init dice, defaults to 3

    Air is used for initiative tiebreakers. Other stats are used for automated rolls.
    """
    if token is not None and len(token) != 1:
        raise discord.ext.commands.BadArgument("Token must be one character")
     
    game = guildgames[ctx.guild.id]
    chardata = {}
    # print(game)help 

    chardata['name'] = name
    chardata['user'] = ctx.author
    chardata['token'] = token

    # print(chardata)

    if stat1 is not None:
        if stat2 is not None:
            if stat3 is not None:
                # 3+ numbers, consider all stats
                chardata['earth'] = stat1
                chardata['air'] = stat2
                chardata['fire'] = stat3
                chardata['water'] = stat4
                chardata['init'] = stat5
            else:
                # 2 numbers, init + air
                chardata['air'] = stat1
                chardata['init'] = stat2
        else:
            # 1 number, just air
            chardata['air'] = stat1
    
    # print(chardata)

    message = game.adduser(**chardata)
    # print(message)
    await ctx.send(message)

mychar.usage = "<name> [token] [(air | earth air fire water)] [init]"




# Startup 

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot.run(open("token.txt").read().strip(), bot=True, reconnect=True)
    log.info("\nPost-run cleanup here\n\n")
    for game in guildgames.values():
        game.save()
