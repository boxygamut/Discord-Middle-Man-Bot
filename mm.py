import discord
from discord import app_commands
from discord.ext import commands, tasks
from typing import Union
import json
import asyncio
from Litecoin import Litecoin



class MiddleMan(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        
        with open("config.json", "r") as f:
            config = json.load(f)
            
        self.fee = (100 - config["fee"])/100  # calculate fee based on what is in the config
        self.channel_naming = config["channel-naming-convention"]
        self.username = config["username"]
        self.password = config["password"]
        
        self.check_payment.start()
        
        
    async def validate_username(self, name:str): # don't think this function is necessary, keeping it anyway
        return name.replace(".", "").replace("_", "")
    
        
    @app_commands.command(name = "create_transaction", description = "Create a transaction with another user")
    @app_commands.describe(user = "User to create transaction with")
    @app_commands.describe(amount = f"Amount in USD")
    @app_commands.describe(role = "Sender or receiver of funds")
    @app_commands.choices(role = [app_commands.Choice(name = "Sender", value = "sender"), app_commands.Choice(name = "Receiver", value = "receiver")])
    async def create_transaction(self, interaction: discord.Interaction, user: discord.Member, amount:float, role:str):
        
        if amount <= 1:
            await interaction.response.send_message("Amount must be greater than $1 USD", ephemeral = True)
            return
        
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel = False)
        }
        
        creator = interaction.user
        
        channel = await interaction.guild.create_text_channel(name = self.channel_naming.replace("[c]", await self.validate_username(creator.name)).replace("[d]", await self.validate_username(user.name)), overwrites = overwrites)
        await channel.set_permissions(creator, send_messages = True, read_messages = True, view_channel = True)
        await channel.set_permissions(user, send_messages = True, read_messages = True, view_channel = True)
        
        await interaction.response.send_message(f"Successfully created channel: `{channel.name}`", ephemeral = True)
        
        transaction = Litecoin(self.username, self.password)
        invoice = transaction.create_invoice(amount)
        
        if not invoice: # check for error
            await channel.send("Something went wrong when creating the invoice, please try again later. Closing the trade in 5 seconds")
            await asyncio.sleep(5)
            await channel.delete()
            return
        
        if role == "sender":
            sender = creator
        else:
            sender = user
            
        if role == "receiver":
            receiver = creator
        else:
            receiver = user
            
        qr_code = discord.File(fp = invoice[1], filename = "invoice_qr.png")
            
        await channel.send(f"Invoice has been created, please pay `{invoice[2]} LTC` to this address: `{invoice[0]}` or scan the QR code shown below", file = qr_code)
        
        with open("transactions.json", "r") as f:
            data = json.load(f)
            
            
        data[str(channel.id)] = {
            "amount": amount,
            "payment_id": invoice[0], # Unique LTC address is used as ID because I'm lazy
            "paid": False,
            "sender": sender.id,
            "receiver": receiver.id
        }
        
        with open("transactions.json", "w+") as f:
            json.dump(data, f, indent = 4)
            
            
        with open("scan.txt", "a") as f:
            f.write("\n" + invoice[0] + ":" + str(invoice[2]))
            
            
    @app_commands.command(name = "complete_transaction", description = "Run in channel to complete the transaction, only the sender can use this")
    async def complete_transaction(self, interaction: discord.Interaction):
        
        with open("transactions.json", "r") as f:
            data = json.load(f)
          
        channel_id = interaction.channel.id
        schannel_id = str(channel_id)
        channel = await self.bot.fetch_channel(channel_id)
        
        if schannel_id in data.keys():
            if data[schannel_id]["sender"] == interaction.user.id:
                receiver = data[schannel_id]["receiver"]
                await interaction.response.send_message(f"<@{receiver}> please send your wallet address, do not send any messages other than your wallet address")
                try:
                    address = await self.bot.wait_for("message", check = lambda m: m.author.id == receiver and m.channel == channel, timeout = 30)
                except asyncio.TimeoutError:
                    await channel.send("Timeout reached, please run the command again when you are ready")
                    return
                
                addy = address.content
                
                if addy.startswith("L") or addy.startswith("M") or addy.startswith("ltc1"):
                    transaction = Litecoin(self.username, self.password)
                    
                    response = transaction.create_payout(amount = data[schannel_id]["amount"] * self.fee, address = addy)
                    
                    if response["status"] == "success":
                        await channel.send(f"Trade complete, sending `${data[schannel_id]['amount']}` to receiver. Funds might take a while to appear in your wallet")
                    else:
                        await channel.send(f"Something happened, please contact an administrator. Error: `{response['error']['message']}`")
                
                else: await interaction.followup.send("Please send a valid LTC address", ephemeral = True)
            
            else: await interaction.response.send_message("Only the person sending the funds can use this command", ephemeral = True)
            
        else: await interaction.response.send_message("You can only use this command in a trade channel", ephemeral = True)


    @tasks.loop(seconds = 5)
    async def check_payment(self):
        with open("scan.txt", "r") as f:
            payment_ids = f.read().splitlines()
            content = f.readlines()
            
        transaction = Litecoin(self.username, self.password)
        
        for payment in payment_ids:
            if payment != "":
                split_string = payment.split(":")
                payment = split_string[0]
                request = transaction.get_transaction(payment, float(split_string[1]))
                
                if request:
                    with open("transactions.json", "r") as f:
                        transactions_list = json.load(f)
                    for channel_id in transactions_list:
                        if transactions_list[channel_id]["payment_id"] == payment:
                            channel = await self.bot.fetch_channel(int(channel_id))
                            transactions_list[channel_id]["paid"] = True
                            with open("transactions.json", "w+") as f:
                                json.dump(transactions_list, f, indent = 4)
                            user = await self.bot.fetch_user(transactions_list[channel_id]["sender"])
                            await channel.send(f"Your payment has been received and is either processing or has been received! {user.mention}")
                            with open("scan.txt", "w") as f:
                                for line in content:
                                    if payment != line:
                                        f.write(line)
            
        
async def setup(bot):
    await bot.add_cog(MiddleMan(bot))