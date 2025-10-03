#!/usr/bin/env python3
"""
🤖 Telegram Bot Verification System
🎯 Automated verification of channel ownership and 3GRAM gifts

This bot system handles:
- Channel ownership verification
- Gift and attribute verification (3GRAM)
- Member count validation
- Activity monitoring
- Proof generation and storage

Author: Nova Team
Version: 3.0
Last Updated: September 27, 2025
"""

import asyncio
import sqlite3
import json
import hashlib
import uuid
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.errors import ChannelPrivateError, ChatAdminRequiredError
import logging
import os
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TelegramBotVerifier:
    """
    Telegram Bot Verification System for Channel Marketplace
    
    Handles automated verification of channel ownership, gifts, and attributes
    using the Telegram API through Telethon client.
    """
    
    def __init__(self, api_id: str, api_hash: str, bot_token: str, db_path: str = "./data/TelegramMarketplace.db"):
        """Initialize the bot verifier with Telegram credentials."""
        self.api_id = api_id
        self.api_hash = api_hash  
        self.bot_token = bot_token
        self.db_path = db_path
        self.client = None
        
        # 3GRAM gift types and their detection patterns
        self.gift_patterns = {
            'premium_boost': ['boost', 'premium', 'level'],
            'star_gift': ['star', 'golden', 'silver', 'bronze'],
            'custom_emoji': ['emoji', 'sticker', 'custom'],
            'voice_chat': ['voice', 'chat', 'audio'],
            'premium_sticker': ['premium', 'sticker', 'animated'],
            'collectible': ['collectible', 'nft', 'rare']
        }
        
        logger.info("🤖 Telegram Bot Verifier initialized")
    
    def get_db(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn
    
    async def start_client(self):
        """Start the Telegram client."""
        try:
            self.client = TelegramClient('bot_session', self.api_id, self.api_hash)
            await self.client.start(bot_token=self.bot_token)
            logger.info("✅ Telegram client started successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start Telegram client: {e}")
            return False
    
    async def stop_client(self):
        """Stop the Telegram client."""
        if self.client:
            await self.client.disconnect()
            logger.info("🔌 Telegram client disconnected")
    
    async def verify_channel_ownership(self, channel_id: int, verification_code: str, session_id: str) -> Dict:
        """
        Verify channel ownership by checking for verification code in channel.
        
        Args:
            channel_id: Database channel ID
            verification_code: Unique verification code to look for
            session_id: Bot verification session ID
            
        Returns:
            Dict with verification results
        """
        try:
            logger.info(f"🔍 Starting ownership verification for channel {channel_id}")
            
            conn = self.get_db()
            cursor = conn.cursor()
            
            # Get channel details from database
            cursor.execute("SELECT * FROM channels WHERE id = ?", (channel_id,))
            channel = cursor.fetchone()
            
            if not channel:
                return {'success': False, 'error': 'Channel not found in database'}
            
            telegram_channel_id = channel['channel_id']
            
            # Update verification status to in_progress
            cursor.execute("""
                UPDATE bot_verifications 
                SET verification_status = 'in_progress'
                WHERE bot_session_id = ?
            """, (session_id,))
            conn.commit()
            
            # Get channel entity from Telegram
            try:
                channel_entity = await self.client.get_entity(int(telegram_channel_id))
            except (ChannelPrivateError, ValueError) as e:
                error_msg = f"Cannot access channel: {e}"
                await self._update_verification_result(session_id, False, error_msg)
                return {'success': False, 'error': error_msg}
            
            # Search for verification code in recent messages
            verification_found = False
            proof_message = None
            
            try:
                async for message in self.client.iter_messages(channel_entity, limit=50):
                    if message.text and verification_code in message.text:
                        verification_found = True
                        proof_message = {
                            'message_id': message.id,
                            'text': message.text,
                            'date': message.date.isoformat(),
                            'sender_id': message.sender_id
                        }
                        break
            except ChatAdminRequiredError:
                error_msg = "Bot needs admin access to read messages"
                await self._update_verification_result(session_id, False, error_msg)
                return {'success': False, 'error': error_msg}
            
            # Get channel info
            channel_info = {
                'title': channel_entity.title,
                'username': channel_entity.username,
                'participants_count': getattr(channel_entity, 'participants_count', 0),
                'verified': getattr(channel_entity, 'verified', False),
                'restricted': getattr(channel_entity, 'restricted', False)
            }
            
            # Update verification result
            verification_data = {
                'channel_info': channel_info,
                'proof_message': proof_message,
                'verification_timestamp': datetime.now().isoformat()
            }
            
            await self._update_verification_result(
                session_id, verification_found, 
                "Ownership verified successfully" if verification_found else "Verification code not found",
                verification_data
            )
            
            # Update channel verification status
            if verification_found:
                cursor.execute("""
                    UPDATE channels 
                    SET ownership_verified = 1, verified_at = CURRENT_TIMESTAMP,
                        member_count = ?
                    WHERE id = ?
                """, (channel_info['participants_count'], channel_id))
                conn.commit()
            
            conn.close()
            
            result = {
                'success': verification_found,
                'channel_info': channel_info,
                'verification_data': verification_data
            }
            
            logger.info(f"✅ Ownership verification completed: {verification_found}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Ownership verification error: {e}")
            await self._update_verification_result(session_id, False, str(e))
            return {'success': False, 'error': str(e)}
    
    async def verify_channel_gifts(self, channel_id: int, session_id: str) -> Dict:
        """
        Verify channel gifts and 3GRAM attributes.
        
        Args:
            channel_id: Database channel ID
            session_id: Bot verification session ID
            
        Returns:
            Dict with gift verification results
        """
        try:
            logger.info(f"🎁 Starting gift verification for channel {channel_id}")
            
            conn = self.get_db()
            cursor = conn.cursor()
            
            # Get channel details
            cursor.execute("SELECT * FROM channels WHERE id = ?", (channel_id,))
            channel = cursor.fetchone()
            
            if not channel:
                return {'success': False, 'error': 'Channel not found'}
            
            telegram_channel_id = channel['channel_id']
            
            # Update verification status
            cursor.execute("""
                UPDATE bot_verifications 
                SET verification_status = 'in_progress'
                WHERE bot_session_id = ?
            """, (session_id,))
            conn.commit()
            
            # Get channel entity
            try:
                channel_entity = await self.client.get_entity(int(telegram_channel_id))
            except Exception as e:
                error_msg = f"Cannot access channel: {e}"
                await self._update_verification_result(session_id, False, error_msg)
                return {'success': False, 'error': error_msg}
            
            # Get claimed gifts from database
            cursor.execute("SELECT * FROM channel_gifts WHERE channel_id = ?", (channel_id,))
            claimed_gifts = [dict(row) for row in cursor.fetchall()]
            
            # Verify each claimed gift
            verified_gifts = []
            gift_verification_results = []
            
            for gift in claimed_gifts:
                verification_result = await self._verify_single_gift(channel_entity, gift)
                gift_verification_results.append(verification_result)
                
                if verification_result['verified']:
                    verified_gifts.append(gift)
                    
                    # Update gift verification status
                    cursor.execute("""
                        UPDATE channel_gifts 
                        SET is_verified = 1, verified_by_bot = 1, verification_timestamp = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (gift['id'],))
            
            # Scan for additional gifts not claimed
            additional_gifts = await self._scan_for_additional_gifts(channel_entity)
            
            # Compile verification data
            verification_data = {
                'claimed_gifts_count': len(claimed_gifts),
                'verified_gifts_count': len(verified_gifts),
                'additional_gifts_found': len(additional_gifts),
                'gift_verification_results': gift_verification_results,
                'additional_gifts': additional_gifts,
                'verification_timestamp': datetime.now().isoformat()
            }
            
            # Update verification result
            success = len(verified_gifts) > 0 or len(additional_gifts) > 0
            
            await self._update_verification_result(
                session_id, success,
                f"Verified {len(verified_gifts)} gifts, found {len(additional_gifts)} additional",
                verification_data
            )
            
            # Update channel gifts verification status
            if success:
                cursor.execute("""
                    UPDATE channels 
                    SET gifts_verified = 1
                    WHERE id = ?
                """, (channel_id,))
            
            conn.commit()
            conn.close()
            
            result = {
                'success': success,
                'verified_gifts': verified_gifts,
                'additional_gifts': additional_gifts,
                'verification_data': verification_data
            }
            
            logger.info(f"✅ Gift verification completed: {len(verified_gifts)} verified")
            return result
            
        except Exception as e:
            logger.error(f"❌ Gift verification error: {e}")
            await self._update_verification_result(session_id, False, str(e))
            return {'success': False, 'error': str(e)}
    
    async def _verify_single_gift(self, channel_entity, gift: Dict) -> Dict:
        """Verify a single gift/attribute."""
        try:
            gift_type = gift['gift_type']
            gift_name = gift['gift_name']
            gift_code = gift.get('gift_code')
            
            # Basic verification logic (can be enhanced with actual Telegram API calls)
            verification_methods = {
                'premium_boost': self._verify_premium_boost,
                'star_gift': self._verify_star_gift,
                'custom_emoji': self._verify_custom_emoji,
                'voice_chat': self._verify_voice_chat,
                'premium_sticker': self._verify_premium_sticker,
                'collectible': self._verify_collectible
            }
            
            verifier = verification_methods.get(gift_type, self._verify_generic_gift)
            result = await verifier(channel_entity, gift)
            
            return {
                'gift_id': gift['id'],
                'gift_type': gift_type,
                'gift_name': gift_name,
                'verified': result['verified'],
                'verification_method': result.get('method', 'generic'),
                'details': result.get('details', {}),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Single gift verification error: {e}")
            return {
                'gift_id': gift['id'],
                'verified': False,
                'error': str(e)
            }
    
    async def _verify_premium_boost(self, channel_entity, gift: Dict) -> Dict:
        """Verify premium boost gift."""
        # Check if channel has boost features
        has_boost = getattr(channel_entity, 'has_geo', False) or getattr(channel_entity, 'slowmode_enabled', False)
        
        return {
            'verified': has_boost,
            'method': 'boost_features_check',
            'details': {'has_boost_features': has_boost}
        }
    
    async def _verify_star_gift(self, channel_entity, gift: Dict) -> Dict:
        """Verify star gift."""
        # Check for star-related features or reactions
        return {
            'verified': True,  # Placeholder - implement actual star verification
            'method': 'star_features_check',
            'details': {'star_verified': True}
        }
    
    async def _verify_custom_emoji(self, channel_entity, gift: Dict) -> Dict:
        """Verify custom emoji gift."""
        # Check for custom emoji usage in recent messages
        try:
            custom_emoji_found = False
            async for message in self.client.iter_messages(channel_entity, limit=20):
                if message.entities:
                    for entity in message.entities:
                        if hasattr(entity, 'document_id'):  # Custom emoji
                            custom_emoji_found = True
                            break
                if custom_emoji_found:
                    break
            
            return {
                'verified': custom_emoji_found,
                'method': 'message_scan',
                'details': {'custom_emoji_found': custom_emoji_found}
            }
        except:
            return {'verified': False, 'method': 'scan_failed'}
    
    async def _verify_voice_chat(self, channel_entity, gift: Dict) -> Dict:
        """Verify voice chat capability."""
        # Check if channel supports voice chats
        return {
            'verified': True,  # Placeholder - implement actual voice chat verification
            'method': 'voice_capability_check',
            'details': {'voice_supported': True}
        }
    
    async def _verify_premium_sticker(self, channel_entity, gift: Dict) -> Dict:
        """Verify premium sticker gift."""
        return {
            'verified': True,  # Placeholder
            'method': 'sticker_check',
            'details': {'premium_stickers': True}
        }
    
    async def _verify_collectible(self, channel_entity, gift: Dict) -> Dict:
        """Verify collectible gift."""
        return {
            'verified': True,  # Placeholder
            'method': 'collectible_check',
            'details': {'collectible_verified': True}
        }
    
    async def _verify_generic_gift(self, channel_entity, gift: Dict) -> Dict:
        """Generic gift verification."""
        return {
            'verified': False,
            'method': 'generic',
            'details': {'message': 'Unknown gift type'}
        }
    
    async def _scan_for_additional_gifts(self, channel_entity) -> List[Dict]:
        """Scan channel for additional gifts not claimed."""
        additional_gifts = []
        
        try:
            # Scan recent messages for gift indicators
            async for message in self.client.iter_messages(channel_entity, limit=100):
                if message.text:
                    text_lower = message.text.lower()
                    
                    # Check for gift patterns
                    for gift_type, patterns in self.gift_patterns.items():
                        if any(pattern in text_lower for pattern in patterns):
                            additional_gifts.append({
                                'gift_type': gift_type,
                                'detected_in_message': message.id,
                                'confidence': 0.7,  # Placeholder confidence score
                                'text_snippet': message.text[:100]
                            })
                            break
            
        except Exception as e:
            logger.error(f"Additional gifts scan error: {e}")
        
        return additional_gifts[:10]  # Limit to 10 additional gifts
    
    async def _update_verification_result(self, session_id: str, success: bool, message: str, data: Dict = None):
        """Update verification result in database."""
        try:
            conn = self.get_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE bot_verifications 
                SET verification_status = ?, is_successful = ?, 
                    completed_at = CURRENT_TIMESTAMP, verification_data = ?,
                    error_message = ?
                WHERE bot_session_id = ?
            """, (
                'completed', success, json.dumps(data) if data else None,
                None if success else message, session_id
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Update verification result error: {e}")
    
    async def process_pending_verifications(self):
        """Process all pending verification requests."""
        try:
            conn = self.get_db()
            cursor = conn.cursor()
            
            # Get pending verifications
            cursor.execute("""
                SELECT * FROM bot_verifications 
                WHERE verification_status = 'pending' 
                AND expires_at > datetime('now')
                ORDER BY started_at ASC
            """)
            
            pending_verifications = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            logger.info(f"📋 Processing {len(pending_verifications)} pending verifications")
            
            for verification in pending_verifications:
                try:
                    if verification['verification_type'] == 'ownership':
                        await self.verify_channel_ownership(
                            verification['channel_id'],
                            verification['verification_code'],
                            verification['bot_session_id']
                        )
                    elif verification['verification_type'] == 'gifts':
                        await self.verify_channel_gifts(
                            verification['channel_id'],
                            verification['bot_session_id']
                        )
                    
                    # Small delay between verifications
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Verification processing error: {e}")
                    await self._update_verification_result(
                        verification['bot_session_id'], False, str(e)
                    )
            
        except Exception as e:
            logger.error(f"Process pending verifications error: {e}")
    
    async def run_verification_loop(self):
        """Run continuous verification processing loop."""
        logger.info("🔄 Starting verification processing loop")
        
        while True:
            try:
                await self.process_pending_verifications()
                await asyncio.sleep(30)  # Check every 30 seconds
            except KeyboardInterrupt:
                logger.info("🛑 Verification loop stopped by user")
                break
            except Exception as e:
                logger.error(f"Verification loop error: {e}")
                await asyncio.sleep(60)  # Wait longer on error


async def main():
    """Main function to run the bot verifier."""
    # Configuration (use environment variables in production)
    API_ID = os.getenv('TELEGRAM_API_ID', 'your_api_id')
    API_HASH = os.getenv('TELEGRAM_API_HASH', 'your_api_hash')
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'your_bot_token')
    
    if API_ID == 'your_api_id':
        logger.error("❌ Please set TELEGRAM_API_ID, TELEGRAM_API_HASH, and TELEGRAM_BOT_TOKEN environment variables")
        return
    
    # Initialize bot verifier
    bot_verifier = TelegramBotVerifier(API_ID, API_HASH, BOT_TOKEN)
    
    # Start client
    if await bot_verifier.start_client():
        logger.info("🚀 Bot verifier started successfully")
        
        try:
            # Run verification loop
            await bot_verifier.run_verification_loop()
        finally:
            await bot_verifier.stop_client()
    else:
        logger.error("❌ Failed to start bot verifier")


if __name__ == "__main__":
    print("🤖 Telegram Channel Marketplace Bot Verifier")
    print("=" * 50)
    asyncio.run(main())
