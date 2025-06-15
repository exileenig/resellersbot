import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
from datetime import datetime
from typing import Optional, List
import aiofiles

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Configuration
ADMIN_ROLE = "Admin"  # Change this to your admin role name
ADMIN_LOG_CHANNEL_ID = None  # Set this to your admin log channel ID
DATA_DIR = "data"
STOCK_DIR = "stock"
LOGS_DIR = "data/logs"

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STOCK_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# Data file paths
USERS_FILE = os.path.join(DATA_DIR, "users.json")
PRODUCTS_FILE = os.path.join(DATA_DIR, "products.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

class DataManager:
    @staticmethod
    async def load_json(file_path: str, default: dict = None) -> dict:
        if default is None:
            default = {}
        try:
            if os.path.exists(file_path):
                async with aiofiles.open(file_path, 'r') as f:
                    content = await f.read()
                    return json.loads(content)
            return default
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            return default

    @staticmethod
    async def save_json(file_path: str, data: dict):
        try:
            async with aiofiles.open(file_path, 'w') as f:
                await f.write(json.dumps(data, indent=2))
        except Exception as e:
            print(f"Error saving {file_path}: {e}")

    @staticmethod
    async def get_user_data(user_id: str) -> dict:
        users = await DataManager.load_json(USERS_FILE)
        return users.get(user_id, {"balance": 0.0, "discount": 0, "total_keys": 0})

    @staticmethod
    async def update_user_data(user_id: str, data: dict):
        users = await DataManager.load_json(USERS_FILE)
        users[user_id] = data
        await DataManager.save_json(USERS_FILE, users)

    @staticmethod
    async def get_products() -> dict:
        return await DataManager.load_json(PRODUCTS_FILE)

    @staticmethod
    async def save_products(products: dict):
        await DataManager.save_json(PRODUCTS_FILE, products)

    @staticmethod
    async def get_config() -> dict:
        return await DataManager.load_json(CONFIG_FILE)

    @staticmethod
    async def save_config(config: dict):
        await DataManager.save_json(CONFIG_FILE, config)

class StockManager:
    @staticmethod
    def get_stock_file(product: str, duration: str) -> str:
        return os.path.join(STOCK_DIR, f"{product}_{duration}.txt")

    @staticmethod
    async def get_stock_count(product: str, duration: str) -> int:
        stock_file = StockManager.get_stock_file(product, duration)
        try:
            if os.path.exists(stock_file):
                async with aiofiles.open(stock_file, 'r') as f:
                    content = await f.read()
                    lines = [line.strip() for line in content.split('\n') if line.strip()]
                    return len(lines)
            return 0
        except Exception as e:
            print(f"Error reading stock file {stock_file}: {e}")
            return 0

    @staticmethod
    async def pull_keys(product: str, duration: str, quantity: int) -> List[str]:
        stock_file = StockManager.get_stock_file(product, duration)
        try:
            if not os.path.exists(stock_file):
                return []
            
            async with aiofiles.open(stock_file, 'r') as f:
                content = await f.read()
                lines = [line.strip() for line in content.split('\n') if line.strip()]
            
            if len(lines) < quantity:
                return []
            
            # Pull keys from the top
            pulled_keys = lines[:quantity]
            remaining_keys = lines[quantity:]
            
            # Write remaining keys back to file
            async with aiofiles.open(stock_file, 'w') as f:
                await f.write('\n'.join(remaining_keys))
            
            return pulled_keys
        except Exception as e:
            print(f"Error pulling keys from {stock_file}: {e}")
            return []

    @staticmethod
    async def add_stock(product: str, duration: str, keys: List[str]):
        stock_file = StockManager.get_stock_file(product, duration)
        try:
            # Append keys to existing stock
            async with aiofiles.open(stock_file, 'a') as f:
                for key in keys:
                    await f.write(f"{key.strip()}\n")
        except Exception as e:
            print(f"Error adding stock to {stock_file}: {e}")

class Logger:
    @staticmethod
    async def log_user_action(user_id: str, action: str):
        log_file = os.path.join(LOGS_DIR, f"user_{user_id}.txt")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {action}\n"
        
        try:
            async with aiofiles.open(log_file, 'a') as f:
                await f.write(log_entry)
        except Exception as e:
            print(f"Error logging user action: {e}")

    @staticmethod
    async def send_admin_log(bot: commands.Bot, message: str):
        if ADMIN_LOG_CHANNEL_ID:
            try:
                channel = bot.get_channel(ADMIN_LOG_CHANNEL_ID)
                if channel:
                    await channel.send(f"```\n{message}\n```")
            except Exception as e:
                print(f"Error sending admin log: {e}")

def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        return any(role.name == ADMIN_ROLE for role in interaction.user.roles)
    return app_commands.check(predicate)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# Admin Commands
@bot.tree.command(name="add_product", description="Add a new product with durations")
@app_commands.describe(name="Product name", durations="Comma-separated durations (e.g., 1Day,1Week,1Month)")
@is_admin()
async def add_product(interaction: discord.Interaction, name: str, durations: str):
    try:
        products = await DataManager.get_products()
        duration_list = [d.strip() for d in durations.split(',')]
        products[name] = duration_list
        await DataManager.save_products(products)
        
        await interaction.response.send_message(f"✅ Added product **{name}** with durations: {', '.join(duration_list)}")
        await Logger.send_admin_log(bot, f"PRODUCT ADDED\nName: {name}\nDurations: {', '.join(duration_list)}\nBy: {interaction.user}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error adding product: {str(e)}")

@bot.tree.command(name="set_price", description="Set price for a product duration")
@app_commands.describe(product="Product name", duration="Duration", price="Price in dollars")
@is_admin()
async def set_price(interaction: discord.Interaction, product: str, duration: str, price: float):
    try:
        config = await DataManager.get_config()
        if product not in config:
            config[product] = {}
        config[product][duration] = price
        await DataManager.save_config(config)
        
        await interaction.response.send_message(f"✅ Set price for **{product} {duration}** to **${price}**")
        await Logger.send_admin_log(bot, f"PRICE SET\nProduct: {product}\nDuration: {duration}\nPrice: ${price}\nBy: {interaction.user}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error setting price: {str(e)}")

@bot.tree.command(name="add_balance", description="Add balance to a user")
@app_commands.describe(user="User to add balance to", amount="Amount to add")
@is_admin()
async def add_balance(interaction: discord.Interaction, user: discord.Member, amount: float):
    try:
        user_data = await DataManager.get_user_data(str(user.id))
        user_data["balance"] += amount
        await DataManager.update_user_data(str(user.id), user_data)
        
        await interaction.response.send_message(f"✅ Added **${amount}** to {user.mention}'s balance. New balance: **${user_data['balance']}**")
        await Logger.send_admin_log(bot, f"BALANCE ADDED\nUser: {user}\nAmount: ${amount}\nNew Balance: ${user_data['balance']}\nBy: {interaction.user}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error adding balance: {str(e)}")

@bot.tree.command(name="remove_balance", description="Remove balance from a user")
@app_commands.describe(user="User to remove balance from", amount="Amount to remove")
@is_admin()
async def remove_balance(interaction: discord.Interaction, user: discord.Member, amount: float):
    try:
        user_data = await DataManager.get_user_data(str(user.id))
        user_data["balance"] = max(0, user_data["balance"] - amount)
        await DataManager.update_user_data(str(user.id), user_data)
        
        await interaction.response.send_message(f"✅ Removed **${amount}** from {user.mention}'s balance. New balance: **${user_data['balance']}**")
        await Logger.send_admin_log(bot, f"BALANCE REMOVED\nUser: {user}\nAmount: ${amount}\nNew Balance: ${user_data['balance']}\nBy: {interaction.user}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error removing balance: {str(e)}")

@bot.tree.command(name="set_discount", description="Set reseller discount for a user")
@app_commands.describe(user="User to set discount for", percent="Discount percentage (0-100)")
@is_admin()
async def set_discount(interaction: discord.Interaction, user: discord.Member, percent: int):
    try:
        if not 0 <= percent <= 100:
            await interaction.response.send_message("❌ Discount must be between 0 and 100")
            return
            
        user_data = await DataManager.get_user_data(str(user.id))
        user_data["discount"] = percent
        await DataManager.update_user_data(str(user.id), user_data)
        
        await interaction.response.send_message(f"✅ Set **{percent}%** discount for {user.mention}")
        await Logger.send_admin_log(bot, f"DISCOUNT SET\nUser: {user}\nDiscount: {percent}%\nBy: {interaction.user}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error setting discount: {str(e)}")

@bot.tree.command(name="stock", description="Upload stock keys from a file")
@app_commands.describe(product="Product name", duration="Duration", file="Text file with keys (one per line)")
@is_admin()
async def stock(interaction: discord.Interaction, product: str, duration: str, file: discord.Attachment):
    try:
        if not file.filename.endswith('.txt'):
            await interaction.response.send_message("❌ Please upload a .txt file")
            return
        
        content = await file.read()
        keys = [line.strip() for line in content.decode('utf-8').split('\n') if line.strip()]
        
        if not keys:
            await interaction.response.send_message("❌ No valid keys found in file")
            return
        
        await StockManager.add_stock(product, duration, keys)
        
        await interaction.response.send_message(f"✅ Added **{len(keys)}** keys to **{product} {duration}** stock")
        await Logger.send_admin_log(bot, f"STOCK ADDED\nProduct: {product}\nDuration: {duration}\nKeys Added: {len(keys)}\nBy: {interaction.user}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error uploading stock: {str(e)}")

@bot.tree.command(name="clear_stock", description="Clear all stock for a product duration")
@app_commands.describe(product="Product name", duration="Duration")
@is_admin()
async def clear_stock(interaction: discord.Interaction, product: str, duration: str):
    try:
        stock_file = StockManager.get_stock_file(product, duration)
        if os.path.exists(stock_file):
            os.remove(stock_file)
            await interaction.response.send_message(f"✅ Cleared stock for **{product} {duration}**")
            await Logger.send_admin_log(bot, f"STOCK CLEARED\nProduct: {product}\nDuration: {duration}\nBy: {interaction.user}")
        else:
            await interaction.response.send_message(f"❌ No stock file found for **{product} {duration}**")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error clearing stock: {str(e)}")

@bot.tree.command(name="stock_status", description="View current stock levels")
@is_admin()
async def stock_status(interaction: discord.Interaction):
    try:
        products = await DataManager.get_products()
        embed = discord.Embed(title="📦 Stock Status", color=0x00ff00)
        
        for product, durations in products.items():
            stock_info = []
            for duration in durations:
                count = await StockManager.get_stock_count(product, duration)
                stock_info.append(f"{duration}: {count} keys")
            embed.add_field(name=product, value="\n".join(stock_info), inline=True)
        
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error getting stock status: {str(e)}")

# Reseller Commands
@bot.tree.command(name="generate", description="Generate keys for a product")
@app_commands.describe(product="Product name", duration="Duration", quantity="Number of keys to generate")
async def generate(interaction: discord.Interaction, product: str, duration: str, quantity: int = 1):
    try:
        if quantity <= 0 or quantity > 10:
            await interaction.response.send_message("❌ Quantity must be between 1 and 10")
            return
        
        # Check if product and duration exist
        products = await DataManager.get_products()
        if product not in products or duration not in products[product]:
            await interaction.response.send_message(f"❌ Product **{product}** with duration **{duration}** not found")
            return
        
        # Get pricing
        config = await DataManager.get_config()
        if product not in config or duration not in config[product]:
            await interaction.response.send_message(f"❌ No price set for **{product} {duration}**")
            return
        
        base_price = config[product][duration]
        user_data = await DataManager.get_user_data(str(interaction.user.id))
        
        # Calculate total cost with discount
        discount_multiplier = (100 - user_data["discount"]) / 100
        total_cost = base_price * quantity * discount_multiplier
        
        # Check balance
        if user_data["balance"] < total_cost:
            await interaction.response.send_message(f"❌ Insufficient balance. Need **${total_cost:.2f}**, have **${user_data['balance']:.2f}**")
            return
        
        # Check stock
        stock_count = await StockManager.get_stock_count(product, duration)
        if stock_count < quantity:
            await interaction.response.send_message(f"❌ Insufficient stock. Requested: **{quantity}**, Available: **{stock_count}**")
            return
        
        # Pull keys
        keys = await StockManager.pull_keys(product, duration, quantity)
        if len(keys) != quantity:
            await interaction.response.send_message("❌ Error pulling keys from stock")
            return
        
        # Deduct balance and update stats
        user_data["balance"] -= total_cost
        user_data["total_keys"] += quantity
        await DataManager.update_user_data(str(interaction.user.id), user_data)
        
        # Create response
        keys_text = "\n".join([f"- {key}" for key in keys])
        embed = discord.Embed(title="🔑 Keys Generated", color=0x00ff00)
        embed.add_field(name="Product", value=f"{product} {duration}", inline=True)
        embed.add_field(name="Quantity", value=str(quantity), inline=True)
        embed.add_field(name="Total Cost", value=f"${total_cost:.2f}", inline=True)
        embed.add_field(name="Remaining Balance", value=f"${user_data['balance']:.2f}", inline=True)
        embed.add_field(name="Keys", value=keys_text, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Log the transaction
        log_message = f"Generated {quantity}x {product} {duration} - Total: ${total_cost:.2f} ({user_data['discount']}% discount applied)"
        await Logger.log_user_action(str(interaction.user.id), log_message)
        
        # Admin log
        admin_log = f"[KEYS GENERATED]\nUser: {interaction.user}\nProduct: {product}\nDuration: {duration}\nQuantity: {quantity}\nTotal: ${total_cost:.2f} ({user_data['discount']}% discount applied)\nRemaining Balance: ${user_data['balance']:.2f}\nKeys:\n{keys_text}"
        await Logger.send_admin_log(bot, admin_log)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Error generating keys: {str(e)}")

@bot.tree.command(name="my_balance", description="Check your balance and discount")
async def my_balance(interaction: discord.Interaction):
    try:
        user_data = await DataManager.get_user_data(str(interaction.user.id))
        embed = discord.Embed(title="💰 Your Account", color=0x0099ff)
        embed.add_field(name="Balance", value=f"${user_data['balance']:.2f}", inline=True)
        embed.add_field(name="Discount", value=f"{user_data['discount']}%", inline=True)
        embed.add_field(name="Total Keys Generated", value=str(user_data['total_keys']), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error getting balance: {str(e)}")

@bot.tree.command(name="prices", description="View all current prices")
async def prices(interaction: discord.Interaction):
    try:
        config = await DataManager.get_config()
        user_data = await DataManager.get_user_data(str(interaction.user.id))
        
        embed = discord.Embed(title="💲 Current Prices", color=0x0099ff)
        
        for product, durations in config.items():
            price_info = []
            for duration, price in durations.items():
                discounted_price = price * (100 - user_data["discount"]) / 100
                price_info.append(f"{duration}: ${price:.2f} → ${discounted_price:.2f}")
            embed.add_field(name=product, value="\n".join(price_info), inline=True)
        
        if user_data["discount"] > 0:
            embed.set_footer(text=f"Prices shown with your {user_data['discount']}% discount applied")
        
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error getting prices: {str(e)}")

@bot.tree.command(name="estimate", description="Estimate cost for a purchase")
@app_commands.describe(product="Product name", duration="Duration", quantity="Number of keys")
async def estimate(interaction: discord.Interaction, product: str, duration: str, quantity: int = 1):
    try:
        config = await DataManager.get_config()
        if product not in config or duration not in config[product]:
            await interaction.response.send_message(f"❌ No price set for **{product} {duration}**")
            return
        
        base_price = config[product][duration]
        user_data = await DataManager.get_user_data(str(interaction.user.id))
        
        discount_multiplier = (100 - user_data["discount"]) / 100
        total_cost = base_price * quantity * discount_multiplier
        savings = (base_price * quantity) - total_cost
        
        embed = discord.Embed(title="💰 Cost Estimate", color=0x0099ff)
        embed.add_field(name="Product", value=f"{product} {duration}", inline=True)
        embed.add_field(name="Quantity", value=str(quantity), inline=True)
        embed.add_field(name="Base Price", value=f"${base_price * quantity:.2f}", inline=True)
        embed.add_field(name="Your Discount", value=f"{user_data['discount']}%", inline=True)
        embed.add_field(name="You Pay", value=f"${total_cost:.2f}", inline=True)
        embed.add_field(name="You Save", value=f"${savings:.2f}", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error calculating estimate: {str(e)}")

@bot.tree.command(name="generate_history", description="Get your purchase history")
async def generate_history(interaction: discord.Interaction):
    try:
        log_file = os.path.join(LOGS_DIR, f"user_{interaction.user.id}.txt")
        
        if not os.path.exists(log_file):
            await interaction.response.send_message("❌ No purchase history found", ephemeral=True)
            return
        
        async with aiofiles.open(log_file, 'r') as f:
            content = await f.read()
        
        if not content.strip():
            await interaction.response.send_message("❌ No purchase history found", ephemeral=True)
            return
        
        # Send as file if too long, otherwise as message
        if len(content) > 1900:
            file = discord.File(log_file, filename=f"purchase_history_{interaction.user.id}.txt")
            await interaction.response.send_message("📋 Your purchase history:", file=file, ephemeral=True)
        else:
            await interaction.response.send_message(f"📋 **Your Purchase History:**\n```\n{content}\n```", ephemeral=True)
            
    except Exception as e:
        await interaction.response.send_message(f"❌ Error getting history: {str(e)}")

# Run the bot
if __name__ == "__main__":
    # Replace with your bot token
    bot.run('YOUR_BOT_TOKEN_HERE')
