import logging
import os
import tempfile
import json

from localutil import debug_id

import wark_global as wg 


# Game data section

class Character:
    """ Represents one character in one FFRPG game. """
    SAVE_FIELDS =  (
        'token', 'name', 'init',
        'earth', 'air', 'fire', 'water',
        'maskearth', 'maskair', 'maskfire', 'maskwater')

    def __init__(self, game, user, *, data=None, **kwargs):
        """ Use data if loading a character, otherwise pretend this is initalize() """
        self.game = game
        self.user = user
    
        if data:
            self.from_data(data)
        else:
            self.initialize(**kwargs)

        
    def initialize(self, *, token=None, name=None, init=None, earth=None, air=None, fire=None, water=None):
        """ Make a new character from given data, initializing un-provided stuff to base state. Therefore also documents what attributes a character should have, along with SAVE_FIELDS. Remember to update both. """

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
        """ Make publically printable character summary. """

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
        """ Become JSON """
        data = {}
        for field in self.SAVE_FIELDS:
            data[field] = getattr(self, field, None)
        data['last_known_dname'] = self.user.name
        data['last_known_gname'] = self.user.display_name
        return data
    
    def from_data(self, data):
        """ Overwrite all data with incoming JSON. Doesn't bother with defaults. Maybe it should to be safer? """
        for field in (field for field in self.SAVE_FIELDS if field not in data):
            cid = debug_id(guild=self.game.guild, user=self.user, charname=data.get('name',None))
            wg.log.warning(f"Character {cid} missing field {field}")

        for field in data:
            # Expects secured data
            setattr(self, field, data[field])

            


class FFGame:
    """ Reprsenents an FFRPG game. Right now, one game per server """
    def __init__(self, guild):
        """ Create a game based on a server/guild ID. Will save/load data based on that ID """
        self.guild = guild
        self.usercharacters = {}
        self.npcs = {}
        wg.log.info(f'Guild {debug_id(guild=guild)} created')
        self.load()

    def adduser(self, user, **kwargs):
        """ Add a new player character tied to the player's ID. Not for NPCs, therefore. """
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
        """ Save all our data in a file named after our guild ID """
        # os.mkdirs(DATADIR, exist_ok=True)
        savefile = os.path.join(wg.DATADIR, str(self.guild.id) + ".json")

        savedata = {
            'userchars': {id:self.usercharacters[id].to_data() for id in self.usercharacters},
            'guildid': self.guild.id,
            'last_known_name': self.guild.name,
        }

        with tempfile.NamedTemporaryFile(mode="w", dir=wg.DATADIR) as outf:
            json.dump(savedata, outf, indent=1)
            if os.path.exists(savefile):
                os.unlink(savefile)
            os.link(outf.name, savefile)

        wg.log.info(f'Guild {debug_id(guild=self.guild)} saved. '
            f'{len(self.usercharacters)} user chars and {len(self.npcs)} npcs.')

        pass

    def load(self):
        """ Load all data given we know our guild ID """

        if self.usercharacters or self.npcs:
            wg.log.critical(f"load() called on active FFGame {debug_id(guild=self.guild)}. "
                "Live data will be overwritten.")
        
        savefile = os.path.join(wg.DATADIR, str(self.guild.id) + ".json")
        if not os.path.isfile(savefile):
            wg.log.info(f'No save data for {debug_id(guild=self.guild)}')
            return
        
        with open(savefile) as inf:
            data = json.load(inf)

        for uid, chardata in data['userchars'].items():
            user = wg.bot.get_user(int(uid))
            if user is None:
                name = chardata.get('last_known_dname', '') 
                cname = chardata.get("name","INVALID")
                wg.log.warning(
                    f'User {debug_id(guild=self.guild, userid=uid, username=name)}'
                    f'not found on discord, dropping character record "{cname}"')
                continue
            self.usercharacters[user.id] = Character(self, user, data=chardata)
        
        wg.log.info(f'Guild {debug_id(guild=self.guild)} loaded. '
            f'{len(self.usercharacters)} user chars and {len(self.npcs)} npcs.')