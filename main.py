import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
from datetime import datetime
from typing import Optional, List
import aiofiles
import logging
import sys

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Configuration
ADMIN_ROLE = os.getenv("ADMIN_ROLE", "Admin")
ADMIN_LOG_CHANNEL_ID = int(os.getenv("ADMIN_LOG_CHANNEL_ID")) if os.getenv("ADMIN_LOG_CHANNEL_ID") else None
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
    def setup_logging():
        """Setup improved logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('bot.log', encoding='utf-8')
            ]
        )
        
        # Reduce discord.py logging noise
        logging.getLogger('discord').setLevel(logging.WARNING)
        logging.getLogger('discord.http').setLevel(logging.WARNING)
        
        return logging.getLogger('bot')

    @staticmethod
    async def log_user_action(user_id: str, action: str, amount: float = None, product: str = None):
        """Enhanced user action logging with better formatting"""
        log_file = os.path.join(LOGS_DIR, f"user_{user_id}.txt")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Format the log entry nicely
        if amount and product:
            log_entry = f"[{timestamp}] 🔑 {action} | Product: {product} | Amount: ${amount:.2f}\n"
        elif amount:
            log_entry = f"[{timestamp}] 💰 {action} | Amount: ${amount:.2f}\n"
        else:
            log_entry = f"[{timestamp}] ℹ️  {action}\n"
        
        try:
            async with aiofiles.open(log_file, 'a') as f:
                await f.write(log_entry)
        except Exception as e:
            logger.error(f"Error logging user action: {e}")

    @staticmethod
    async def send_admin_log(bot: commands.Bot, message: str):
        """Send formatted admin logs"""
        if ADMIN_LOG_CHANNEL_ID:
            try:
                channel = bot.get_channel(ADMIN_LOG_CHANNEL_ID)
                if channel:
                    # Create a nice embed for admin logs
                    embed = discord.Embed(
                        title="🔧 Admin Log",
                        description=f"```\n{message}\n```",
                        color=discord.Color.orange(),
                        timestamp=datetime.now()
                    )
                    await channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Error sending admin log: {e}")

# Initialize logger
logger = Logger.setup_logging()

# =========================[ AUTOCOMPLETE FUNCTIONS ]=========================
async def product_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    products = await DataManager.get_products()
    return [
        app_commands.Choice(name=product, value=product)
        for product in products.keys()
        if current.lower() in product.lower()
    ][:25]

async def duration_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    # Get the product from the interaction if available
    try:
        product = interaction.namespace.product
        products = await DataManager.get_products()
        if product in products:
            durations = products[product]
        else:
            # Fallback to all possible durations
            config = await DataManager.get_config()
            durations = set()
            for product_durations in config.values():
                durations.update(product_durations.keys())
            durations = list(durations)
    except:
        # Fallback to common durations
        durations = ["1 Day", "1 Week", "1 Month", "Lifetime"]
    
    return [
        app_commands.Choice(name=duration, value=duration)
        for duration in durations
        if current.lower() in duration.lower()
    ][:25]

# =========================[ COPY KEYS BUTTON VIEW ]=========================
class CopyKeysView(discord.ui.View):
    def __init__(self, keys: list[str]):
        super().__init__(timeout=180)
        self.keys = keys

    @discord.ui.button(label="📋 Copy all keys", style=discord.ButtonStyle.primary)
    async def copy_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        all_keys = "\n".join(self.keys)
        
        embed = discord.Embed(
            title="📋 All Generated Keys",
            description="Here are all your generated license keys (raw format):",
            color=discord.Color.blue()
        )
        
        # Split keys into chunks if there are many to avoid embed limits
        key_chunks = []
        current_chunk = []
        current_length = 0
        
        for key in self.keys:
            if current_length + len(key) > 1000:  # Discord embed field limit
                key_chunks.append("\n".join(current_chunk))
                current_chunk = [key]
                current_length = len(key)
            else:
                current_chunk.append(key)
                current_length += len(key) + 1
        
        if current_chunk:
            key_chunks.append("\n".join(current_chunk))
        
        # Add chunks as fields
        for i, chunk in enumerate(key_chunks):
            field_name = "License Keys" if i == 0 else f"License Keys (continued {i+1})"
            embed.add_field(name=field_name, value=f"```\n{chunk}\n```", inline=False)
        
        embed.set_footer(text="Copy the raw keys from above")
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

# =========================[ CONFIRM GENERATE VIEW ]=========================
class ConfirmGenerateView(discord.ui.View):
    def __init__(self, user_id: int, product: str, duration: str, quantity: int, 
                 base_price: float, total_cost: float, discount: float):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.product = product
        self.duration = duration
        self.quantity = quantity
        self.base_price = base_price
        self.total_cost = total_cost
        self.discount = discount

    @discord.ui.button(label="🔑 Generate Keys", style=discord.ButtonStyle.success)
    async def generate_keys(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ You cannot confirm this generation.", ephemeral=True)
            return

        current_balance = (await DataManager.get_user_data(str(self.user_id)))["balance"]
        if current_balance < self.total_cost:
            embed = discord.Embed(
                title="❌ Insufficient Balance",
                description="Your balance is insufficient.",
                color=discord.Color.red()
            )
            embed.timestamp = discord.utils.utcnow()
            embed.set_footer(text="Powered by MyBot")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Check stock
        stock_count = await StockManager.get_stock_count(self.product, self.duration)
        if stock_count < self.quantity:
            embed = discord.Embed(
                title="❌ Insufficient Stock",
                description=f"Requested: **{self.quantity}**, Available: **{stock_count}**",
                color=discord.Color.red()
            )
            embed.timestamp = discord.utils.utcnow()
            embed.set_footer(text="Powered by MyBot")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Pull keys
        keys = await StockManager.pull_keys(self.product, self.duration, self.quantity)
        if len(keys) != self.quantity:
            embed = discord.Embed(
                title="❌ Error Pulling Keys",
                description="Error pulling keys from stock",
                color=discord.Color.red()
            )
            embed.timestamp = discord.utils.utcnow()
            embed.set_footer(text="Powered by MyBot")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Deduct balance and update stats
        user_data = await DataManager.get_user_data(str(self.user_id))
        user_data["balance"] -= self.total_cost
        user_data["total_keys"] += self.quantity
        await DataManager.update_user_data(str(self.user_id), user_data)

        # Create result embed matching your style
        result_embed = discord.Embed(
            title="✅ License Keys Generated",
            description="Your license keys have been generated successfully!",
            color=discord.Color.green()
        )
        
        # Add each key as a separate field (matching your style)
        for i, key in enumerate(keys):
            result_embed.add_field(
                name=f"Key {i+1}",
                value=f"\n```{key}```\n",
                inline=False
            )
        
        result_embed.add_field(name="⏱️ Duration", value=self.duration, inline=True)
        result_embed.add_field(name="💰 Total Cost", value=f"${self.total_cost:.2f}", inline=True)
        result_embed.add_field(name="💸 New Balance", value=f"${user_data['balance']:.2f}", inline=True)
        
        result_embed.set_footer(text="Thank you for using our service!")
        result_embed.timestamp = discord.utils.utcnow()
        
        view = CopyKeysView(keys)
        await interaction.response.send_message(embed=result_embed, view=view, ephemeral=True)
        
        # Log the transaction
        log_message = f"Generated {self.quantity}x {self.product} {self.duration} ({self.discount}% discount applied)"
        await Logger.log_user_action(str(self.user_id), log_message, self.total_cost, f"{self.product} {self.duration}")
        
        # Admin log
        keys_text = "\n".join([f"• {key}" for key in keys])
        admin_log = f"[KEYS GENERATED]\n👤 User: {interaction.user.display_name} ({interaction.user.id})\n🎯 Product: {self.product} {self.duration}\n📊 Quantity: {self.quantity}\n💰 Total: ${self.total_cost:.2f} ({self.discount}% discount)\n💵 Remaining Balance: ${user_data['balance']:.2f}\n🔑 Keys Generated:\n{keys_text}"
        await Logger.send_admin_log(bot, admin_log)
        
        # Console log
        logger.info(f"✅ Keys generated: {interaction.user.display_name} bought {self.quantity}x {self.product} {self.duration} for ${self.total_cost:.2f}")

    @discord.ui.button(label="❌ Cancel Generation", style=discord.ButtonStyle.secondary)
    async def cancel_generation(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ You cannot cancel this generation.", ephemeral=True)
            return
        await interaction.response.send_message("License generation cancelled.", ephemeral=True)

# =========================[ PAGINATOR VIEW ]=========================
def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        return any(role.name == ADMIN_ROLE for role in interaction.user.roles)
    return app_commands.check(predicate)

@bot.event
async def on_ready():
    logger.info(f'🤖 {bot.user} has connected to Discord!')
    logger.info(f'📊 Bot is in {len(bot.guilds)} servers')
    logger.info(f'👥 Serving {sum(guild.member_count for guild in bot.guilds)} users')
    
    try:
        synced = await bot.tree.sync()
        logger.info(f'✅ Synced {len(synced)} slash command(s)')
    except Exception as e:
        logger.error(f'❌ Failed to sync commands: {e}')

@bot.event
async def on_command_error(ctx, error):
    logger.error(f'Command error in {ctx.command}: {error}')

@bot.event
async def on_application_command_error(interaction: discord.Interaction, error):
    logger.error(f'Slash command error in {interaction.command}: {error}')
    if not interaction.response.is_done():
        await interaction.response.send_message("❌ An error occurred while processing your command.", ephemeral=True)

# =========================[ BALANCE SYSTEM COMMAND ]=========================

# =========================[ PRICES COMMAND ]=========================
@bot.tree.command(name="prices", description="View all current prices 💲")
async def prices(interaction: discord.Interaction):
    try:
        config = await DataManager.get_config()
        user_data = await DataManager.get_user_data(str(interaction.user.id))
        
        embed = discord.Embed(
            title="💲 Current Prices",
            description="All available products and their pricing",
            color=discord.Color.yellow()
        )
        
        for product, durations in config.items():
            price_info = []
            for duration, price in durations.items():
                stock_count = await StockManager.get_stock_count(product, duration)
                if user_data["discount"] > 0:
                    discounted_price = price * (100 - user_data["discount"]) / 100
                    original_price = f"~~${price:.2f}~~" if user_data["discount"] > 0 else ""
                    price_info.append(f"**{duration}**\n> {original_price} ${discounted_price:.2f}\n> Stock: {stock_count} keys")
                else:
                    price_info.append(f"**{duration}**\n> ${price:.2f}\n> Stock: {stock_count} keys")
            
            embed.add_field(
                name=f"🎯 {product}",
                value="\n".join(price_info),
                inline=True
            )
        
        embed.add_field(name="💰 Your Balance", value=f"${user_data['balance']:.2f}", inline=True)
        embed.add_field(name="🎫 Your Discount", value=f"{user_data['discount']}%", inline=True)
        embed.add_field(name="📊 Total Keys Generated", value=str(user_data['total_keys']), inline=True)
        
        embed.set_footer(text="Powered by MyBot")
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error getting prices: {str(e)}")

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
        await Logger.send_admin_log(bot, f"[PRODUCT ADDED]\n📦 Product: {name}\n⏱️  Durations: {', '.join(duration_list)}\n👤 By: {interaction.user.display_name}")
        logger.info(f"➕ Product added: {name} with durations {', '.join(duration_list)} by {interaction.user.display_name}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error adding product: {str(e)}")

@bot.tree.command(name="set_price", description="Set price for a product duration")
@app_commands.describe(product="Product name", duration="Duration", price="Price in dollars")
@app_commands.autocomplete(product=product_autocomplete, duration=duration_autocomplete)
@is_admin()
async def set_price(interaction: discord.Interaction, product: str, duration: str, price: float):
    try:
        config = await DataManager.get_config()
        if product not in config:
            config[product] = {}
        config[product][duration] = price
        await DataManager.save_config(config)
        
        await interaction.response.send_message(f"✅ Set price for **{product} {duration}** to **${price}**")
        await Logger.send_admin_log(bot, f"[PRICE SET]\n🎯 Product: {product} {duration}\n💰 Price: ${price}\n👤 By: {interaction.user.display_name}")
        logger.info(f"💲 Price set: {product} {duration} = ${price} by {interaction.user.display_name}")
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
        await Logger.send_admin_log(bot, f"[BALANCE ADDED]\n👤 User: {user.display_name} ({user.id})\n💰 Amount: ${amount}\n💵 New Balance: ${user_data['balance']}\n🔧 By: {interaction.user.display_name}")
        logger.info(f"💰 Balance added: ${amount} to {user.display_name} by {interaction.user.display_name}")
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
        await Logger.send_admin_log(bot, f"[BALANCE REMOVED]\n👤 User: {user.display_name} ({user.id})\n💰 Amount: ${amount}\n💵 New Balance: ${user_data['balance']}\n🔧 By: {interaction.user.display_name}")
        logger.info(f"💸 Balance removed: ${amount} from {user.display_name} by {interaction.user.display_name}")
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
        await Logger.send_admin_log(bot, f"[DISCOUNT SET]\n👤 User: {user.display_name} ({user.id})\n🎫 Discount: {percent}%\n🔧 By: {interaction.user.display_name}")
        logger.info(f"🎫 Discount set: {percent}% for {user.display_name} by {interaction.user.display_name}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error setting discount: {str(e)}")

@bot.tree.command(name="stock", description="Upload stock keys from a file")
@app_commands.describe(product="Product name", duration="Duration", file="Text file with keys (one per line)")
@app_commands.autocomplete(product=product_autocomplete, duration=duration_autocomplete)
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
        await Logger.send_admin_log(bot, f"[STOCK ADDED]\n🎯 Product: {product} {duration}\n🔑 Keys Added: {len(keys)}\n👤 By: {interaction.user.display_name}")
        logger.info(f"📦 Stock added: {len(keys)} keys for {product} {duration} by {interaction.user.display_name}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error uploading stock: {str(e)}")

@bot.tree.command(name="clear_stock", description="Clear all stock for a product duration")
@app_commands.describe(product="Product name", duration="Duration")
@app_commands.autocomplete(product=product_autocomplete, duration=duration_autocomplete)
@is_admin()
async def clear_stock(interaction: discord.Interaction, product: str, duration: str):
    try:
        stock_file = StockManager.get_stock_file(product, duration)
        if os.path.exists(stock_file):
            os.remove(stock_file)
            await interaction.response.send_message(f"✅ Cleared stock for **{product} {duration}**")
            await Logger.send_admin_log(bot, f"[STOCK CLEARED]\n🎯 Product: {product} {duration}\n👤 By: {interaction.user.display_name}")
            logger.info(f"🗑️ Stock cleared: {product} {duration} by {interaction.user.display_name}")
        else:
            await interaction.response.send_message(f"❌ No stock file found for **{product} {duration}**")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error clearing stock: {str(e)}")

@bot.tree.command(name="stock_status", description="View current stock levels")
@is_admin()
async def stock_status(interaction: discord.Interaction):
    try:
        products = await DataManager.get_products()
        config = await DataManager.get_config()
        
        embed = discord.Embed(
            title="📦 Stock Status",
            description="Current inventory levels for all products",
            color=discord.Color.green()
        )
        
        total_keys = 0
        total_value = 0.0
        
        for product, durations in products.items():
            stock_info = []
            for duration in durations:
                count = await StockManager.get_stock_count(product, duration)
                total_keys += count
                
                # Calculate value if price exists
                if product in config and duration in config[product]:
                    value = count * config[product][duration]
                    total_value += value
                    stock_info.append(f"**{duration}**\n> Keys: {count}\n> Value: ${value:.2f}")
                else:
                    stock_info.append(f"**{duration}**\n> Keys: {count}\n> Value: N/A")
            
            embed.add_field(
                name=f"🎯 {product}",
                value="\n".join(stock_info),
                inline=True
            )
        
        embed.add_field(name="📊 Total Keys", value=str(total_keys), inline=True)
        embed.add_field(name="💰 Total Value", value=f"${total_value:.2f}", inline=True)
        embed.add_field(name="📈 Products", value=str(len(products)), inline=True)
        
        embed.set_footer(text="Powered by MyBot")
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error getting stock status: {str(e)}")

# Reseller Commands
@bot.tree.command(name="generate", description="Generate keys for a product")
@app_commands.describe(product="Product name", duration="Duration", quantity="Number of keys to generate")
@app_commands.autocomplete(product=product_autocomplete, duration=duration_autocomplete)
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
        
        # Confirm generation
        view = ConfirmGenerateView(interaction.user.id, product, duration, quantity, base_price, total_cost, user_data["discount"])
        
        embed = discord.Embed(
            title="🔑 Confirm License Generation",
            description=f"Are you sure you want to generate **{quantity}x {product} {duration}** licenses?",
            color=discord.Color.yellow()
        )
        embed.add_field(name="Base Price", value=f"${base_price:.2f} each", inline=True)
        embed.add_field(name="Quantity", value=str(quantity), inline=True)
        embed.add_field(name="Discount", value=f"{user_data['discount']}%", inline=True)
        embed.add_field(name="Total Cost", value=f"${total_cost:.2f}", inline=True)
        embed.add_field(name="Your Balance", value=f"${user_data['balance']:.2f}", inline=True)
        embed.set_footer(text="Powered by MyBot")
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
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

@bot.tree.command(name="estimate", description="Estimate cost for a purchase")
@app_commands.describe(product="Product name", duration="Duration", quantity="Number of keys")
@app_commands.autocomplete(product=product_autocomplete, duration=duration_autocomplete)
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
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("❌ DISCORD_BOT_TOKEN not found in environment variables")
        logger.error("🔧 Please set DISCORD_BOT_TOKEN in Replit Secrets")
        logger.error("🌐 Get your token from: https://discord.com/developers/applications")
        exit(1)
    
    try:
        logger.info("🚀 Starting Discord bot...")
        bot.run(token, log_handler=None)  # We handle logging ourselves
    except discord.LoginFailure:
        logger.error("❌ Invalid Discord bot token")
        logger.error("🔧 Please check your DISCORD_BOT_TOKEN in Replit Secrets")
        logger.error("🌐 Make sure you copied the full token from https://discord.com/developers/applications")
    except KeyboardInterrupt:
        logger.info("⏹️ Bot shutdown requested by user")
    except Exception as e:
        logger.error(f"💥 Error starting bot: {e}")
