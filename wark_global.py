import logging

""" Thread-global data objects. The big index of data by server index for persistence might be a little icky to store this way, but this is what I have it seems x.x """

DATADIR = "./guild_data"

log = logging.getLogger()
guildgames = {}
bot = None