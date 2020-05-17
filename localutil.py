import discord
import dicewark

def debug_id(
    guild: discord.Guild=None, guildid: int=None, guildname: str="",
    user: discord.User=None, userid: int=None, username: str="", charname: str=""):

    useguild = any((guild,guildid,guildname))
    useuser = any((user,userid,username))
    usechar = bool(charname)

    if guild:
        guildid = guild.id
        guildname = guild.name
    else:
        guild = dicewark.bot.get_guild(guildid) if guildid is not None else None
        if guild:
            guildname = guild.name
        else:
            guildid = "<Invalid Server>"
    
    if user:
        userid = user.id
        username = user.name
    else:
        user = dicewark.bot.get_user(userid) if userid is not None else None
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
    c_out = f'{charname}' if usechar else ''

    
    out = f'{c_out}{" of " if c_out and (u_out or g_out) else ""}{u_out}{" from " if u_out and g_out else ""}{g_out}'

    
    return(out)