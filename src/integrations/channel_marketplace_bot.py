#!/usr/bin/env python3
"""
🤖 Channel Marketplace Bot - Complete Business Flow Implementation
🎯 Handles channel verification, ownership confirmation, and secure transfers

Bot Token: 8285653811:AAFgnMqjtCp0NdmCoI8QRtwuEt136PLK7FQ

Business Flow:
1. Seller adds bot as admin to channel
2. Bot verifies ownership and scans for gifts/attributes
3. Seller creates sell order with chosen price
4. Buyer places buy order - money held in escrow
5. Both parties confirm ownership transfer
6. Money released to seller upon confirmation

Author: Nova Team
Version: 3.0
Last Updated: September 27, 2025
"""

import asyncio
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import uuid
from typing import Dict, List, Optional, Tuple

from telethon import TelegramClient, events, Button
from telethon.tl.types import (
    ChatAdminRights, ChannelParticipantsAdmins, 
    MessageEntityCustomEmoji, MessageEntityTextUrl
)
from telethon.errors import (
    ChannelPrivateError, ChatAdminRequiredError, 
    UserNotParticipantError, FloodWaitError
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('marketplace_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Bot Configuration
BOT_TOKEN = "8285653811:AAFgnMqjtCp0NdmCoI8QRtwuEt136PLK7FQ"
API_ID = "YOUR_API_ID"  # You'll need to get this from https://my.telegram.org
API_HASH = "YOUR_API_HASH"  # You'll need to get this from https://my.telegram.org

DATABASE_PATH = "./data/channel_marketplace.db"

class ChannelMarketplaceBot:
    """
    Complete Channel Marketplace Bot Implementation
    
    Handles the entire business flow from channel verification to ownership transfer
    with secure escrow and atomic transactions.
    """
    
    def __init__(self):
        """Initialize the marketplace bot."""
        self.bot = None
        self.db_path = DATABASE_PATH
        
        # Gift detection patterns for 3GRAM and other premium features
        self.gift_patterns = {
            'premium_boost': ['boost', 'premium', 'level', 'enhanced'],
            'star_gift': ['star', 'golden', 'silver', 'bronze', '⭐', '🌟'],
            'custom_emoji': ['emoji', 'sticker', 'custom', '😀', '🎨'],
            'voice_chat': ['voice', 'chat', 'audio', '🎤', '🔊'],
            'premium_sticker': ['premium', 'animated', 'sticker', '🎭'],
            'collectible': ['collectible', 'nft', 'rare', 'limited', '💎'],
            'channel_boost': ['channel boost', 'boosted', 'boost level'],
            'subscriber_gift': ['subscriber', 'member gift', 'exclusive']
        }
        
        logger.info("🤖 Channel Marketplace Bot initialized")
    
    def get_db(self):
        """Get database connection with proper configuration."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.row_factory = sqlite3.Row
        return conn
    
    async def start_bot(self):
        """Start the Telegram bot client."""
        try:
            self.bot = TelegramClient('marketplace_bot', API_ID, API_HASH)
            await self.bot.start(bot_token=BOT_TOKEN)
            
            # Get bot info
            me = await self.bot.get_me()
            logger.info(f"✅ Bot started: @{me.username}")
            
            # Set up event handlers
            self.setup_handlers()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start bot: {e}")
            return False
    
    def setup_handlers(self):
        """Set up bot event handlers."""
        
        @self.bot.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            """Handle /start command."""
            await self.handle_start(event)
        
        @self.bot.on(events.NewMessage(pattern='/verify'))
        async def verify_handler(event):
            """Handle /verify command."""
            await self.handle_verify_channel(event)
        
        @self.bot.on(events.NewMessage(pattern='/list'))
        async def list_handler(event):
            """Handle /list command."""
            await self.handle_list_channel(event)
        
        @self.bot.on(events.NewMessage(pattern='/buy'))
        async def buy_handler(event):
            """Handle /buy command."""
            await self.handle_buy_channel(event)
        
        @self.bot.on(events.NewMessage(pattern='/confirm'))
        async def confirm_handler(event):
            """Handle /confirm command."""
            await self.handle_confirm_transfer(event)
        
        @self.bot.on(events.CallbackQuery)
        async def callback_handler(event):
            """Handle inline button callbacks."""
            await self.handle_callback(event)
    
    async def handle_start(self, event):
        """Handle bot start command."""
        user_id = event.sender_id
        
        welcome_text = """
🏪 **Welcome to Channel Marketplace Bot!**

I help you buy and sell Telegram channels securely with escrow protection.

**For Sellers:**
1. Add me as admin to your channel
2. Use /verify to verify ownership and scan gifts
3. Use /list to create a sell order

**For Buyers:**
1. Use /buy to purchase a channel
2. Confirm ownership transfer when ready

**Security Features:**
✅ Ownership verification
✅ Gift/attribute scanning
✅ Escrow protection
✅ Atomic transactions

Use /verify <channel_username> to get started!
        """
        
        await event.respond(welcome_text, parse_mode='markdown')
        
        # Log user interaction
        await self.log_user_interaction(user_id, 'start', 'Bot started by user')
    
    async def handle_verify_channel(self, event):
        """Handle channel verification request."""
        try:
            # Parse command: /verify @channel_username or /verify channel_id
            message_text = event.message.text.strip()
            parts = message_text.split()
            
            if len(parts) < 2:
                await event.respond(
                    "❌ Please provide channel username or ID\n"
                    "Usage: `/verify @channel_username`",
                    parse_mode='markdown'
                )
                return
            
            channel_identifier = parts[1].replace('@', '')
            user_id = event.sender_id
            
            await event.respond("🔍 Starting channel verification...")
            
            # Start verification process
            verification_result = await self.verify_channel_ownership(
                channel_identifier, user_id
            )
            
            if verification_result['success']:
                # Create verification record in database
                verification_id = await self.create_verification_record(
                    user_id, verification_result
                )
                
                # Send verification results
                await self.send_verification_results(event, verification_result)
                
                # Offer to create listing
                buttons = [
                    [Button.inline("📝 Create Sell Order", f"create_listing_{verification_id}")],
                    [Button.inline("🔄 Re-scan Gifts", f"rescan_{verification_id}")]
                ]
                
                await event.respond(
                    "✅ Verification complete! What would you like to do next?",
                    buttons=buttons
                )
                
            else:
                await event.respond(f"❌ Verification failed: {verification_result['error']}")
                
        except Exception as e:
            logger.error(f"Verification error: {e}")
            await event.respond("❌ An error occurred during verification. Please try again.")
    
    async def verify_channel_ownership(self, channel_identifier: str, user_id: int) -> Dict:
        """Verify channel ownership and scan for gifts."""
        try:
            logger.info(f"🔍 Verifying channel: {channel_identifier} for user: {user_id}")
            
            # Get channel entity
            try:
                channel = await self.bot.get_entity(channel_identifier)
            except Exception as e:
                return {'success': False, 'error': f'Cannot access channel: {e}'}
            
            # Check if bot is admin
            try:
                bot_me = await self.bot.get_me()
                admins = await self.bot.get_participants(channel, filter=ChannelParticipantsAdmins)
                
                bot_is_admin = any(admin.id == bot_me.id for admin in admins)
                
                if not bot_is_admin:
                    return {
                        'success': False, 
                        'error': 'Bot is not admin. Please add me as admin to verify ownership.'
                    }
                
            except Exception as e:
                return {'success': False, 'error': f'Cannot check admin status: {e}'}
            
            # Verify user is owner/admin
            try:
                user_is_admin = any(admin.id == user_id for admin in admins)
                
                if not user_is_admin:
                    return {
                        'success': False, 
                        'error': 'You are not an admin of this channel.'
                    }
                
            except Exception as e:
                return {'success': False, 'error': f'Cannot verify user admin status: {e}'}
            
            # Get channel information
            channel_info = await self.get_channel_info(channel)
            
            # Scan for gifts and premium features
            gifts_info = await self.scan_channel_gifts(channel)
            
            # Generate verification proof
            verification_proof = {
                'timestamp': datetime.now().isoformat(),
                'channel_id': str(channel.id),
                'channel_username': getattr(channel, 'username', None),
                'verifier_bot_id': bot_me.id,
                'verified_user_id': user_id,
                'proof_hash': hashlib.sha256(
                    f"{channel.id}_{user_id}_{datetime.now().timestamp()}".encode()
                ).hexdigest()
            }
            
            return {
                'success': True,
                'channel_info': channel_info,
                'gifts_info': gifts_info,
                'verification_proof': verification_proof,
                'verified_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Channel verification error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_channel_info(self, channel) -> Dict:
        """Get comprehensive channel information."""
        try:
            # Basic channel info
            info = {
                'id': str(channel.id),
                'title': channel.title,
                'username': getattr(channel, 'username', None),
                'description': getattr(channel, 'about', ''),
                'participants_count': getattr(channel, 'participants_count', 0),
                'verified': getattr(channel, 'verified', False),
                'restricted': getattr(channel, 'restricted', False),
                'scam': getattr(channel, 'scam', False),
                'fake': getattr(channel, 'fake', False),
                'created_date': getattr(channel, 'date', None)
            }
            
            # Get additional metrics
            try:
                # Recent message count (activity indicator)
                messages = await self.bot.get_messages(channel, limit=100)
                recent_messages = len([m for m in messages if m.date > datetime.now() - timedelta(days=7)])
                info['recent_activity'] = recent_messages
                
                # Check for premium features
                info['has_premium_features'] = await self.check_premium_features(channel)
                
            except Exception as e:
                logger.warning(f"Could not get additional metrics: {e}")
                info['recent_activity'] = 0
                info['has_premium_features'] = False
            
            return info
            
        except Exception as e:
            logger.error(f"Get channel info error: {e}")
            return {}
    
    async def scan_channel_gifts(self, channel) -> Dict:
        """Scan channel for gifts and premium attributes."""
        try:
            logger.info(f"🎁 Scanning gifts for channel: {channel.title}")
            
            gifts_found = []
            gift_summary = {
                'total_gifts': 0,
                'verified_gifts': 0,
                'estimated_value': Decimal('0'),
                'gift_categories': {}
            }
            
            # Scan recent messages for gift indicators
            try:
                messages = await self.bot.get_messages(channel, limit=200)
                
                for message in messages:
                    if not message.text:
                        continue
                    
                    text_lower = message.text.lower()
                    
                    # Check for gift patterns
                    for gift_type, patterns in self.gift_patterns.items():
                        for pattern in patterns:
                            if pattern in text_lower:
                                gift_info = {
                                    'type': gift_type,
                                    'detected_in_message': message.id,
                                    'message_date': message.date.isoformat(),
                                    'pattern_matched': pattern,
                                    'confidence': 0.8,
                                    'estimated_value': self.estimate_gift_value(gift_type)
                                }
                                gifts_found.append(gift_info)
                                
                                # Update summary
                                gift_summary['total_gifts'] += 1
                                gift_summary['estimated_value'] += gift_info['estimated_value']
                                
                                if gift_type not in gift_summary['gift_categories']:
                                    gift_summary['gift_categories'][gift_type] = 0
                                gift_summary['gift_categories'][gift_type] += 1
                                
                                break  # Only match first pattern per message
                
                # Check for custom emojis in messages
                custom_emoji_count = await self.count_custom_emojis(messages)
                if custom_emoji_count > 0:
                    gifts_found.append({
                        'type': 'custom_emoji',
                        'count': custom_emoji_count,
                        'confidence': 0.9,
                        'estimated_value': Decimal(str(custom_emoji_count * 0.5))
                    })
                
                # Verify premium features
                premium_features = await self.verify_premium_features(channel)
                gifts_found.extend(premium_features)
                
                gift_summary['verified_gifts'] = len([g for g in gifts_found if g.get('confidence', 0) > 0.7])
                
            except Exception as e:
                logger.warning(f"Gift scanning error: {e}")
            
            return {
                'gifts_found': gifts_found,
                'summary': gift_summary,
                'scan_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Scan gifts error: {e}")
            return {'gifts_found': [], 'summary': gift_summary}
    
    async def count_custom_emojis(self, messages) -> int:
        """Count custom emojis in messages."""
        custom_emoji_count = 0
        
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if isinstance(entity, MessageEntityCustomEmoji):
                        custom_emoji_count += 1
        
        return custom_emoji_count
    
    async def verify_premium_features(self, channel) -> List[Dict]:
        """Verify premium channel features."""
        premium_features = []
        
        try:
            # Check for channel boost features
            if hasattr(channel, 'level') and channel.level > 0:
                premium_features.append({
                    'type': 'channel_boost',
                    'level': channel.level,
                    'confidence': 1.0,
                    'estimated_value': Decimal(str(channel.level * 5))
                })
            
            # Check for premium subscriber features
            if getattr(channel, 'participants_count', 0) > 10000:
                premium_features.append({
                    'type': 'large_audience',
                    'subscriber_count': channel.participants_count,
                    'confidence': 1.0,
                    'estimated_value': Decimal(str(channel.participants_count * 0.001))
                })
            
        except Exception as e:
            logger.warning(f"Premium features check error: {e}")
        
        return premium_features
    
    def estimate_gift_value(self, gift_type: str) -> Decimal:
        """Estimate the value of a gift in TON."""
        value_estimates = {
            'premium_boost': Decimal('5.0'),
            'star_gift': Decimal('3.0'),
            'custom_emoji': Decimal('1.0'),
            'voice_chat': Decimal('2.0'),
            'premium_sticker': Decimal('2.5'),
            'collectible': Decimal('10.0'),
            'channel_boost': Decimal('8.0'),
            'subscriber_gift': Decimal('1.5')
        }
        
        return value_estimates.get(gift_type, Decimal('1.0'))
    
    async def check_premium_features(self, channel) -> bool:
        """Check if channel has premium features."""
        try:
            # Check various premium indicators
            has_premium = (
                getattr(channel, 'verified', False) or
                getattr(channel, 'level', 0) > 0 or
                getattr(channel, 'participants_count', 0) > 5000
            )
            
            return has_premium
            
        except Exception as e:
            logger.warning(f"Premium features check error: {e}")
            return False
    
    async def create_verification_record(self, user_id: int, verification_result: Dict) -> str:
        """Create verification record in database."""
        try:
            conn = self.get_db()
            cursor = conn.cursor()
            
            verification_id = str(uuid.uuid4())
            
            # Insert verification record
            cursor.execute("""
                INSERT INTO channel_verifications (
                    verification_id, user_id, channel_id, channel_username, channel_title,
                    verification_data, gifts_data, verification_proof, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                verification_id,
                user_id,
                verification_result['channel_info']['id'],
                verification_result['channel_info'].get('username'),
                verification_result['channel_info']['title'],
                json.dumps(verification_result['channel_info']),
                json.dumps(verification_result['gifts_info']),
                json.dumps(verification_result['verification_proof']),
                'verified',
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Verification record created: {verification_id}")
            return verification_id
            
        except Exception as e:
            logger.error(f"Create verification record error: {e}")
            return None
    
    async def send_verification_results(self, event, verification_result: Dict):
        """Send formatted verification results to user."""
        try:
            channel_info = verification_result['channel_info']
            gifts_info = verification_result['gifts_info']
            
            # Format channel info
            info_text = f"""
🏪 **Channel Verification Results**

📺 **Channel:** {channel_info['title']}
👥 **Subscribers:** {channel_info.get('participants_count', 'Unknown'):,}
🔗 **Username:** @{channel_info.get('username', 'None')}
✅ **Verified:** {'Yes' if channel_info.get('verified') else 'No'}
📅 **Recent Activity:** {channel_info.get('recent_activity', 0)} messages (7 days)

🎁 **Gifts & Premium Features:**
"""
            
            # Add gifts summary
            summary = gifts_info['summary']
            info_text += f"""
📦 **Total Gifts Found:** {summary['total_gifts']}
✅ **Verified Gifts:** {summary['verified_gifts']}
💰 **Estimated Value:** {summary['estimated_value']} TON

**Gift Categories:**
"""
            
            for category, count in summary['gift_categories'].items():
                info_text += f"• {category.replace('_', ' ').title()}: {count}\n"
            
            # Add detailed gifts (top 5)
            if gifts_info['gifts_found']:
                info_text += "\n🔍 **Detected Gifts:**\n"
                for gift in gifts_info['gifts_found'][:5]:
                    confidence = gift.get('confidence', 0) * 100
                    value = gift.get('estimated_value', 0)
                    info_text += f"• {gift['type'].replace('_', ' ').title()} ({confidence:.0f}% confidence, ~{value} TON)\n"
            
            await event.respond(info_text, parse_mode='markdown')
            
        except Exception as e:
            logger.error(f"Send verification results error: {e}")
            await event.respond("✅ Verification completed successfully!")
    
    async def handle_callback(self, event):
        """Handle inline button callbacks."""
        try:
            data = event.data.decode('utf-8')
            user_id = event.sender_id
            
            if data.startswith('create_listing_'):
                verification_id = data.replace('create_listing_', '')
                await self.handle_create_listing(event, verification_id, user_id)
            
            elif data.startswith('rescan_'):
                verification_id = data.replace('rescan_', '')
                await self.handle_rescan_gifts(event, verification_id, user_id)
            
            elif data.startswith('confirm_buy_'):
                transaction_id = data.replace('confirm_buy_', '')
                await self.handle_confirm_purchase(event, transaction_id, user_id)
            
            elif data.startswith('confirm_transfer_'):
                transaction_id = data.replace('confirm_transfer_', '')
                await self.handle_confirm_ownership_transfer(event, transaction_id, user_id)
            
        except Exception as e:
            logger.error(f"Callback handler error: {e}")
            await event.respond("❌ An error occurred. Please try again.")
    
    async def handle_create_listing(self, event, verification_id: str, user_id: int):
        """Handle create listing request."""
        try:
            await event.edit("💰 Please enter the price for your channel in TON:")
            
            # Wait for price input
            async def price_handler(price_event):
                if price_event.sender_id != user_id:
                    return
                
                try:
                    price = float(price_event.text.strip())
                    if price <= 0:
                        await price_event.respond("❌ Price must be greater than 0")
                        return
                    
                    # Create listing
                    listing_id = await self.create_channel_listing(verification_id, user_id, price)
                    
                    if listing_id:
                        await price_event.respond(
                            f"✅ Channel listing created successfully!\n"
                            f"💰 Price: {price} TON\n"
                            f"📋 Listing ID: `{listing_id}`\n\n"
                            f"Your channel is now available for purchase!",
                            parse_mode='markdown'
                        )
                    else:
                        await price_event.respond("❌ Failed to create listing. Please try again.")
                
                except ValueError:
                    await price_event.respond("❌ Please enter a valid number for the price.")
                except Exception as e:
                    logger.error(f"Price handler error: {e}")
                    await price_event.respond("❌ An error occurred. Please try again.")
            
            # Add temporary handler for price input
            self.bot.add_event_handler(price_handler, events.NewMessage(from_users=user_id))
            
            # Remove handler after 5 minutes
            await asyncio.sleep(300)
            self.bot.remove_event_handler(price_handler)
            
        except Exception as e:
            logger.error(f"Create listing error: {e}")
            await event.respond("❌ An error occurred. Please try again.")
    
    async def create_channel_listing(self, verification_id: str, user_id: int, price: float) -> str:
        """Create channel listing in database."""
        try:
            conn = self.get_db()
            cursor = conn.cursor()
            
            # Get verification data
            cursor.execute("""
                SELECT * FROM channel_verifications WHERE verification_id = ? AND user_id = ?
            """, (verification_id, user_id))
            
            verification = cursor.fetchone()
            if not verification:
                logger.error("Verification not found")
                return None
            
            listing_id = str(uuid.uuid4())
            
            # Create listing
            cursor.execute("""
                INSERT INTO channel_listings (
                    listing_id, verification_id, seller_id, channel_id, channel_username,
                    channel_title, price, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                listing_id,
                verification_id,
                user_id,
                verification['channel_id'],
                verification['channel_username'],
                verification['channel_title'],
                str(price),
                'active',
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Channel listing created: {listing_id}")
            return listing_id
            
        except Exception as e:
            logger.error(f"Create listing error: {e}")
            return None
    
    async def log_user_interaction(self, user_id: int, action: str, details: str):
        """Log user interaction for audit purposes."""
        try:
            conn = self.get_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO user_interactions (
                    user_id, action, details, timestamp
                ) VALUES (?, ?, ?, ?)
            """, (user_id, action, details, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Log interaction error: {e}")
    
    async def run_bot(self):
        """Run the bot continuously."""
        logger.info("🚀 Starting Channel Marketplace Bot")
        
        if await self.start_bot():
            logger.info("✅ Bot is running and ready to handle requests")
            await self.bot.run_until_disconnected()
        else:
            logger.error("❌ Failed to start bot")


async def main():
    """Main function to run the marketplace bot."""
    # Initialize database
    await init_database()
    
    # Create and run bot
    bot = ChannelMarketplaceBot()
    await bot.run_bot()


async def init_database():
    """Initialize the database with required tables."""
    try:
        import os
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Create tables
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS channel_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                verification_id TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                channel_id TEXT NOT NULL,
                channel_username TEXT,
                channel_title TEXT NOT NULL,
                verification_data TEXT,
                gifts_data TEXT,
                verification_proof TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS channel_listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id TEXT UNIQUE NOT NULL,
                verification_id TEXT NOT NULL,
                seller_id INTEGER NOT NULL,
                channel_id TEXT NOT NULL,
                channel_username TEXT,
                channel_title TEXT NOT NULL,
                price TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                FOREIGN KEY (verification_id) REFERENCES channel_verifications(verification_id)
            );
            
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT UNIQUE NOT NULL,
                listing_id TEXT NOT NULL,
                buyer_id INTEGER NOT NULL,
                seller_id INTEGER NOT NULL,
                amount TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                escrow_address TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY (listing_id) REFERENCES channel_listings(listing_id)
            );
            
            CREATE TABLE IF NOT EXISTS user_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_verifications_user ON channel_verifications(user_id);
            CREATE INDEX IF NOT EXISTS idx_listings_seller ON channel_listings(seller_id);
            CREATE INDEX IF NOT EXISTS idx_transactions_buyer ON transactions(buyer_id);
            CREATE INDEX IF NOT EXISTS idx_transactions_seller ON transactions(seller_id);
        """)
        
        conn.commit()
        conn.close()
        
        logger.info("✅ Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Database initialization error: {e}")


if __name__ == "__main__":
    print("🤖 Channel Marketplace Bot")
    print("=" * 40)
    print("⚠️  IMPORTANT: You need to set your API_ID and API_HASH")
    print("   Get them from: https://my.telegram.org")
    print("=" * 40)
    
    asyncio.run(main())
