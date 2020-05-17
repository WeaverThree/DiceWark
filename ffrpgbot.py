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

# Files for persisting data
# Trusted files, assuming no attacks on host stystem, minimal correctness checking.

DATADIR = "./guild_data"

log = logging.getLogger()

# Game data section

class DiscordUserNotFound(Exception):
    pass


def debug_id(
    guild: discord.Guild=None, guildid: int=None, guildname: str="",
    user: discord.User=None, userid: int=None, username: str="", charname: str=""):

    useguild = any(guild,guildid,guildname)
    useuser = any(user,userid,username)

    if guild:
        guildid = guild.id
        guildname = guild.name
    else:
        guild = bot.get_guild(guildid) if guildid is not None else None
        if guild:
            guildname = guild.name
        else:
            guildid = "<Invalid Server>"
    
    if user:
        userid = user.id
        username = user.name
    else:
        user = bot.get_user(userid) if userid is not None else None
        if user:
            username=user.name
        else:
            userid = "<Invalid User>"
    
    if not guildname:
        guildname = "<Unknown Server>"

    if not username:
        username = "<Unknown User>"

    if not charname:
        charname = "<Unknown Character>"
    

    g_out = f'{guildname} ({guildid})' if useguild else ''
    u_out = f'{username} ({userid})' if useuser else ''

    
    out = f'{charname}{" of " if charname else ""}{u_out}{" from " if u_out and g_out else ""}{g_out}'

    
    return(out)






class Character:
    SAVE_FIELDS =  (
        'token', 'name', 'init',
        'earth', 'air', 'fire', 'water',
        'maskearth', 'maskair', 'maskfire', 'maskwater')

    def __init__(self, game, user, *, data=None, **kwargs):

        self.game = game
        self.user = user
    
        if data:
            self.from_data(data)
        else:
            self.initialize(**kwargs)

        
    def initialize(self, *, token=None, name=None, init=None, earth=None, air=None, fire=None, water=None):
        self.name = name if name else self.user.name
        self.token = token if token else self.name[0]
        self.earth = earth if earth else 0
        self.air = air if air else 0
        self.fire = fire if fire else 0
        self.water = water if water else 0
        self.init = init if init else 3
        self.maskearth = False
        self.maskair = False
        self.maskfire = False
        self.maskwater = False
    
    def format(self):

        earth = "???" if self.maskearth else self.earth
        air = "???" if self.maskair else self.air
        fire = "???" if self.maskfire else self.fire
        water = "???" if self.maskwater else self.water

        if any((self.earth, self.fire, self.water)):
            statsline = f'Stats: {earth}/{air}/{fire}/{water}'
        elif self.air:
            statsline = f'Air: {air}'
        else:
            statsline = ''

        return (
            f'Character {self.name}, [{self.token}]. '
            f'Init: {self.init} {statsline} Owner: {self.user.name}'
        )
    
    def to_data(self):
        data = {}
        for field in self.SAVE_FIELDS:
            data[field] = getattr(self, field, None)
        data['last_known_dname'] = self.user.name
        data['last_known_gname'] = self.user.display_name
        return data
    
    def from_data(self, data):
        for field in (field for field in self.SAVE_FIELDS if field not in data):
            cid = debug_id(guild=self.game.guild, user=self.user, charname=data.get('name',None))
            log.warning(f"Character {cid} missing field {field}")

        for field in data:
            # Expects secured data
            setattr(self, field, data[field])

            


class FFGame:
    def __init__(self, guild):
        self.guild = guild
        self.usercharacters = {}
        self.npcs = {}
        print(f'Guild {guild.id} for {guild.name} created')
        self.load()
        # load from file if exists

    def adduser(self, user, **kwargs):
        uid = user.id
        oldchar = None
        if uid in self.usercharacters:
            oldchar = self.usercharacters[uid]
        newchar = Character(self, user, **kwargs)
        self.usercharacters[uid] = newchar
        message = []
        message.append(f'New character: {newchar.format()}')
        if oldchar:
            message.append(f'Replaces: {oldchar.format()}')
        return '\n'.join(message)
    
    def save(self):
        # os.mkdirs(DATADIR, exist_ok=True)
        savefile = os.path.join(DATADIR, str(self.guild.id) + ".json")

        savedata = {
            'userchars': {id:self.usercharacters[id].to_data() for id in self.usercharacters},
            'guildid': self.guild.id,
            'last_known_name': self.guild.name,
        }

        with tempfile.NamedTemporaryFile(mode="w", dir=DATADIR) as outf:
            json.dump(savedata, outf, indent=1)
            if os.path.exists(savefile):
                os.unlink(savefile)
            os.link(outf.name, savefile)

        pass

    def load(self):

        if self.usercharacters or self.npcs:
            log.critical(f"load() called on active FFGame {self.guild.id} {self.guild.name}. "
                "Live data will be overwritten.")
        
        savefile = os.path.join(DATADIR, str(self.guild.id) + ".json")
        if not os.path.isfile(savefile):
            return
        
        with open(savefile) as inf:
            data = json.load(inf)

        for uid, chardata in data['userchars'].items():
            print(uid, chardata)
            user = bot.get_user(int(uid))
            if user is None:
                name = chardata.get('last_known_dname', '') 
                log.warning(
                    f'User ID {user} {"last known as" if name else "--NAME UNKNOWN--"} {name} "'
                    f'not found on discord, dropping character record')
                continue
            self.usercharacters[user.id] = Character(self, user, data=chardata)
            

        
    
    

# Thread-global datastore for all this async crap
guildgames = {}

# Discord Interface Section

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

    print(f'\n\nLogged in as: {bot.user.name} - {bot.user.id}\nVersion: {discord.__version__}\n')

    for guild in bot.guilds:
        guildgames[guild.id] = FFGame(guild)


    await bot.change_presence(activity=discord.CustomActivity(name='Test Bot'))
    print(f'Successfully logged in and booted...!')

@bot.command()
@commands.guild_only()
async def roll(ctx, *, expression):
    """Says when a member joined."""
    result = xdice.roll(expression)
    output = []
    for score in result.scores():
        output.append(f'{score}: {score.format(verbose=True)}')
    output = '\n'.join(output)
    await ctx.send(f'{ctx.author.mention}: {output}')


@bot.event
async def on_command_error(ctx, exception):
    usage=""
    if ctx.command is not None and ctx.command.signature:
        usage= f'`{ctx.prefix}{ctx.invoked_with} {ctx.command.signature}`'
    await ctx.send(f'**{type(exception).__name__}**: {" ".join(exception.args)}{usage}'[:1999], delete_after=60*5)
 

    print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)

    traceback.print_exception(type(exception), exception, exception.__traceback__, file=sys.stderr)

# @bot.event
# async def on_error(ename, ctx, exception):
#     out = []
#     for x in dir(exception):
#         out.append(f"{x} -- {getattr(exception,x)}")
#     out = '\n'.join(out)
#     await ctx.send(f"Error:\n{out}")
#     print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
    
#     traceback.print_exception(type(exception), exception, exception.__traceback__, file=sys.stderr)


@bot.command()
@commands.is_owner()
async def shutdown(ctx):
    await ctx.send("Shutting down...")
    print(f'Accepting shutdown request from {ctx.author} ...')
    await ctx.bot.close()

@bot.command()
async def save(ctx):
    for game in guildgames.values():
        game.save()
    await ctx.send("Saved.")    
  
@bot.command()
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot.run(open("token.txt").read().strip(), bot=True, reconnect=True)
    print("Post-run cleanup here?")
    for game in guildgames.values():
        game.save()

