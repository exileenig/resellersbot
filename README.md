# Discord Key Bot

A comprehensive Discord bot for managing product keys and reseller operations.

## Features

### Admin Commands
- `/add_product` - Add new products with durations
- `/set_price` - Set pricing for product durations
- `/add_balance` / `/remove_balance` - Manage user balances
- `/set_discount` - Set reseller discounts
- `/stock` - Upload stock keys from files
- `/clear_stock` - Clear stock for products
- `/stock_status` - View current stock levels

### Reseller Commands
- `/generate` - Purchase and generate keys
- `/my_balance` - Check balance and discount
- `/prices` - View all current prices
- `/estimate` - Calculate purchase costs
- `/generate_history` - View purchase history

## Setup

1. Install dependencies:
   \`\`\`bash
   pip install -r requirements.txt
   \`\`\`

2. Create a Discord application and bot at https://discord.com/developers/applications

3. Update the configuration in `main.py`:
   - Replace `YOUR_BOT_TOKEN_HERE` with your bot token
   - Set `ADMIN_ROLE` to your admin role name
   - Set `ADMIN_LOG_CHANNEL_ID` to your admin log channel ID

4. Invite the bot to your server with the following permissions:
   - Send Messages
   - Use Slash Commands
   - Attach Files
   - Read Message History

5. Run the bot:
   \`\`\`bash
   python main.py
   \`\`\`

## Directory Structure

\`\`\`
bot/
├── main.py                 # Main bot file
├── data/
│   ├── users.json         # User balances, discounts, stats
│   ├── products.json      # Available products and durations
│   ├── config.json        # Pricing configuration
│   └── logs/
│       └── user_*.txt     # Individual user purchase logs
├── stock/
│   └── Product_Duration.txt  # Stock files (one key per line)
└── requirements.txt       # Python dependencies
\`\`\`

## Stock Management

- Stock files are named `Product_Duration.txt` (e.g., `Fortnite_1Day.txt`)
- Each line in a stock file contains one license key
- Keys are pulled from the top of the file when generated
- Empty lines are automatically filtered out

## Logging

- All admin actions are logged to the configured admin channel
- User purchase history is saved to individual log files
- Timestamps are included in all log entries

## Security Notes

- Keep your bot token secure and never commit it to version control
- Regularly backup your data files
- Monitor the admin log channel for suspicious activity
- Consider implementing rate limiting for high-value operations
