import discord
from discord.ext import commands
import json


client = commands.Bot(command_prefix = "!", intents = discord.Intents.all()) # Change intents after completed
extension_list = ["mm"]


@client.event
async def on_ready():
    
    for extension in extension_list:
        await client.load_extension(extension)
    
    print("Bot Online!")
    
@client.command()
async def sync(ctx):
    synced = await client.tree.sync()
    await ctx.send(f"Synced {len(synced)} commands!")
    
@client.command()
async def close(ctx):
    await ctx.channel.delete()
    
@client.command()
async def test(ctx):
    count = 0
    while True:
        count += 1
        print(count)
        
@client.command()
async def ping(ctx):
    await ctx.send("Pong!")
    
with open("config.json", "r") as f:
    data = json.load(f)
    
client.run(data["TOKEN"])