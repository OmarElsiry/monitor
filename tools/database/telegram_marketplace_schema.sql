-- 📱 Telegram Channel Marketplace Database Schema
-- 🎯 A comprehensive database system for buying/selling Telegram channels
-- with gift verification, escrow payments, and dispute resolution
-- 
-- Database: TelegramMarketplace.db
-- Version: 3.0
-- Last Updated: September 27, 2025

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- =====================================================
-- 1. 👥 USERS TABLE - Enhanced user management
-- =====================================================
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id TEXT UNIQUE NOT NULL,
    username TEXT,
    full_name TEXT,
    
    -- Wallet addresses (all variants for TON compatibility)
    main_wallet_address TEXT UNIQUE NOT NULL,
    variant_address_1 TEXT,
    variant_address_2 TEXT,
    variant_address_3 TEXT,
    variant_address_4 TEXT,
    
    -- User roles and status
    user_type TEXT DEFAULT 'buyer' CHECK(user_type IN ('buyer', 'seller', 'both', 'admin')),
    verification_status TEXT DEFAULT 'unverified' CHECK(verification_status IN ('unverified', 'verified', 'premium')),
    kyc_completed BOOLEAN DEFAULT 0,
    
    -- Statistics
    total_sales INTEGER DEFAULT 0,
    total_purchases INTEGER DEFAULT 0,
    seller_rating DECIMAL(3,2) DEFAULT 0.00 CHECK(seller_rating >= 0 AND seller_rating <= 5),
    buyer_rating DECIMAL(3,2) DEFAULT 0.00 CHECK(buyer_rating >= 0 AND buyer_rating <= 5),
    
    -- Account status
    is_active BOOLEAN DEFAULT 1,
    is_banned BOOLEAN DEFAULT 0,
    ban_reason TEXT,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active_at DATETIME,
    verified_at DATETIME
);

-- Users table indexes
CREATE INDEX idx_users_telegram ON users(telegram_id);
CREATE INDEX idx_users_wallets ON users(main_wallet_address, variant_address_1, variant_address_2, variant_address_3, variant_address_4);
CREATE INDEX idx_users_type ON users(user_type);
CREATE INDEX idx_users_status ON users(verification_status);

-- =====================================================
-- 2. 📺 CHANNELS TABLE - Telegram channels for sale
-- =====================================================
CREATE TABLE channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT UNIQUE NOT NULL, -- Telegram channel ID
    channel_username TEXT UNIQUE, -- @channelname
    channel_title TEXT NOT NULL,
    channel_description TEXT,
    
    -- Owner information
    seller_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Channel metrics
    member_count INTEGER NOT NULL CHECK(member_count >= 0),
    active_members INTEGER CHECK(active_members >= 0),
    daily_views_avg INTEGER CHECK(daily_views_avg >= 0),
    engagement_rate DECIMAL(5,2) CHECK(engagement_rate >= 0 AND engagement_rate <= 100),
    created_date DATE,
    
    -- Pricing (in TON)
    asking_price DECIMAL(20,9) NOT NULL CHECK(asking_price > 0),
    minimum_price DECIMAL(20,9) CHECK(minimum_price > 0),
    price_negotiable BOOLEAN DEFAULT 1,
    
    -- Channel categories
    category TEXT NOT NULL CHECK(category IN ('crypto', 'news', 'entertainment', 'gaming', 'education', 'business', 'lifestyle', 'technology', 'other')),
    subcategory TEXT,
    language TEXT DEFAULT 'en',
    
    -- Listing status
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft', 'pending_verification', 'active', 'sold', 'suspended', 'expired')),
    visibility TEXT DEFAULT 'public' CHECK(visibility IN ('public', 'private', 'premium_only')),
    
    -- Verification
    ownership_verified BOOLEAN DEFAULT 0,
    gifts_verified BOOLEAN DEFAULT 0,
    admin_approved BOOLEAN DEFAULT 0,
    verification_token TEXT UNIQUE, -- for ownership verification
    
    -- Featured listing
    is_featured BOOLEAN DEFAULT 0,
    featured_until DATETIME,
    
    -- Statistics
    view_count INTEGER DEFAULT 0,
    favorite_count INTEGER DEFAULT 0,
    
    -- Timestamps
    listed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    sold_at DATETIME,
    expires_at DATETIME,
    verified_at DATETIME
);

-- Channels table indexes
CREATE INDEX idx_channels_seller ON channels(seller_id);
CREATE INDEX idx_channels_status ON channels(status);
CREATE INDEX idx_channels_category ON channels(category);
CREATE INDEX idx_channels_price ON channels(asking_price);
CREATE INDEX idx_channels_verified ON channels(ownership_verified, gifts_verified);
CREATE INDEX idx_channels_featured ON channels(is_featured, featured_until);

-- =====================================================
-- 3. 🎁 CHANNEL_GIFTS TABLE - Track channel gifts and 3GRAM attributes
-- =====================================================
CREATE TABLE channel_gifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    
    -- Gift identification
    gift_type TEXT NOT NULL CHECK(gift_type IN ('premium_boost', 'star_gift', 'custom_emoji', 'voice_chat', 'premium_sticker', 'collectible', 'other')),
    gift_name TEXT NOT NULL,
    gift_code TEXT, -- 3GRAM code if applicable
    
    -- Gift details
    quantity INTEGER DEFAULT 1 CHECK(quantity > 0),
    duration_months INTEGER CHECK(duration_months > 0), -- for time-limited gifts
    value_ton DECIMAL(20,9) CHECK(value_ton >= 0), -- estimated value in TON
    
    -- Verification
    is_verified BOOLEAN DEFAULT 0,
    verified_by_bot BOOLEAN DEFAULT 0,
    verification_timestamp DATETIME,
    verification_proof TEXT, -- screenshot hash or proof
    
    -- Gift status
    is_active BOOLEAN DEFAULT 1,
    is_transferable BOOLEAN DEFAULT 1,
    expires_at DATETIME,
    
    -- Metadata
    description TEXT,
    special_conditions TEXT,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Channel gifts indexes
CREATE INDEX idx_gifts_channel ON channel_gifts(channel_id);
CREATE INDEX idx_gifts_type ON channel_gifts(gift_type);
CREATE INDEX idx_gifts_verified ON channel_gifts(is_verified);
CREATE INDEX idx_gifts_active ON channel_gifts(is_active);

-- =====================================================
-- 4. 🤖 BOT_VERIFICATIONS TABLE - Track bot verification attempts
-- =====================================================
CREATE TABLE bot_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    
    -- Verification details
    verification_type TEXT NOT NULL CHECK(verification_type IN ('ownership', 'gifts', 'members', 'activity')),
    verification_status TEXT DEFAULT 'pending' CHECK(verification_status IN ('pending', 'in_progress', 'completed', 'failed')),
    
    -- Bot session
    bot_session_id TEXT UNIQUE,
    verification_code TEXT UNIQUE, -- unique code for this verification
    
    -- Results
    is_successful BOOLEAN DEFAULT 0,
    error_message TEXT,
    verification_data TEXT, -- JSON string with detailed results
    
    -- Gift verification specifics
    gifts_found INTEGER DEFAULT 0,
    gifts_verified INTEGER DEFAULT 0,
    gift_details TEXT, -- JSON string with detailed gift information
    
    -- Proof
    proof_screenshots TEXT, -- comma-separated file paths
    proof_hash TEXT, -- blockchain hash if stored
    
    -- Attempts
    attempt_count INTEGER DEFAULT 1,
    max_attempts INTEGER DEFAULT 3,
    
    -- Timestamps
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    expires_at DATETIME
);

-- Bot verifications indexes
CREATE INDEX idx_bot_verif_channel ON bot_verifications(channel_id);
CREATE INDEX idx_bot_verif_user ON bot_verifications(user_id);
CREATE INDEX idx_bot_verif_status ON bot_verifications(verification_status);
CREATE INDEX idx_bot_verif_session ON bot_verifications(bot_session_id);

-- =====================================================
-- 5. 💰 TRANSACTIONS TABLE - Enhanced marketplace transactions
-- =====================================================
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_hash TEXT UNIQUE,
    
    -- Transaction parties
    buyer_id INTEGER REFERENCES users(id),
    seller_id INTEGER REFERENCES users(id),
    channel_id INTEGER REFERENCES channels(id),
    
    -- Transaction details
    transaction_type TEXT NOT NULL CHECK(transaction_type IN ('channel_purchase', 'deposit', 'withdrawal', 'escrow', 'refund', 'fee', 'commission')),
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'in_escrow', 'processing', 'completed', 'failed', 'refunded', 'disputed')),
    
    -- Amounts (in TON)
    amount DECIMAL(20,9) NOT NULL CHECK(amount > 0),
    fee_amount DECIMAL(20,9) DEFAULT 0 CHECK(fee_amount >= 0),
    escrow_amount DECIMAL(20,9) DEFAULT 0 CHECK(escrow_amount >= 0),
    final_amount DECIMAL(20,9) CHECK(final_amount >= 0), -- after fees
    
    -- Blockchain details
    from_address TEXT NOT NULL,
    to_address TEXT NOT NULL,
    block_number INTEGER,
    logical_time INTEGER,
    utime INTEGER,
    
    -- Escrow management
    escrow_status TEXT CHECK(escrow_status IN ('locked', 'released', 'refunded')),
    escrow_release_date DATETIME,
    auto_release_date DATETIME, -- automatic release after X days
    
    -- Payment details
    payment_method TEXT DEFAULT 'TON' CHECK(payment_method IN ('TON', 'USDT_TRC20', 'BTC', 'ETH')),
    exchange_rate DECIMAL(10,4), -- if non-TON payment
    
    -- Dispute handling
    is_disputed BOOLEAN DEFAULT 0,
    dispute_id INTEGER REFERENCES disputes(id),
    dispute_resolution TEXT,
    
    -- Metadata
    memo TEXT,
    comment TEXT,
    invoice_id TEXT,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed_at DATETIME,
    completed_at DATETIME,
    blockchain_timestamp INTEGER
);

-- Transactions indexes
CREATE INDEX idx_trans_buyer ON transactions(buyer_id);
CREATE INDEX idx_trans_seller ON transactions(seller_id);
CREATE INDEX idx_trans_channel ON transactions(channel_id);
CREATE INDEX idx_trans_status ON transactions(status);
CREATE INDEX idx_trans_hash ON transactions(transaction_hash);
CREATE INDEX idx_trans_escrow ON transactions(escrow_status);
CREATE INDEX idx_trans_type ON transactions(transaction_type);

-- =====================================================
-- 6. 🤝 CHANNEL_TRANSFERS TABLE - Track ownership transfers
-- =====================================================
CREATE TABLE channel_transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    transaction_id INTEGER REFERENCES transactions(id),
    
    -- Transfer parties
    from_user_id INTEGER NOT NULL REFERENCES users(id),
    to_user_id INTEGER NOT NULL REFERENCES users(id),
    
    -- Transfer details
    transfer_status TEXT DEFAULT 'pending' CHECK(transfer_status IN ('pending', 'in_progress', 'completed', 'failed', 'reversed')),
    transfer_type TEXT DEFAULT 'sale' CHECK(transfer_type IN ('sale', 'gift', 'inheritance', 'admin_action')),
    
    -- Verification
    ownership_transferred BOOLEAN DEFAULT 0,
    admin_rights_transferred BOOLEAN DEFAULT 0,
    gifts_transferred BOOLEAN DEFAULT 0,
    
    -- Transfer process
    transfer_token TEXT UNIQUE, -- secure token for transfer
    transfer_instructions TEXT,
    
    -- Completion details
    completed_steps TEXT, -- JSON string tracking multi-step transfer process
    pending_steps TEXT, -- JSON string
    
    -- Security
    requires_2fa BOOLEAN DEFAULT 1,
    otp_verified BOOLEAN DEFAULT 0,
    
    -- Timestamps
    initiated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    expires_at DATETIME
);

-- Channel transfers indexes
CREATE INDEX idx_transfer_channel ON channel_transfers(channel_id);
CREATE INDEX idx_transfer_transaction ON channel_transfers(transaction_id);
CREATE INDEX idx_transfer_users ON channel_transfers(from_user_id, to_user_id);
CREATE INDEX idx_transfer_status ON channel_transfers(transfer_status);

-- =====================================================
-- 7. 💬 DISPUTES TABLE - Handle transaction disputes
-- =====================================================
CREATE TABLE disputes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    channel_id INTEGER REFERENCES channels(id),
    
    -- Dispute parties
    initiator_id INTEGER NOT NULL REFERENCES users(id),
    respondent_id INTEGER NOT NULL REFERENCES users(id),
    
    -- Dispute details
    dispute_type TEXT NOT NULL CHECK(dispute_type IN ('non_delivery', 'misrepresentation', 'gift_missing', 'member_count', 'payment_issue', 'fraud', 'other')),
    status TEXT DEFAULT 'open' CHECK(status IN ('open', 'under_review', 'resolved', 'escalated', 'closed')),
    priority TEXT DEFAULT 'normal' CHECK(priority IN ('low', 'normal', 'high', 'urgent')),
    
    -- Dispute content
    reason TEXT NOT NULL,
    description TEXT,
    evidence TEXT, -- JSON string with links to evidence files
    
    -- Resolution
    resolution TEXT CHECK(resolution IN ('refund_full', 'refund_partial', 'transfer_completed', 'rejected')),
    resolution_notes TEXT,
    refund_amount DECIMAL(20,9) CHECK(refund_amount >= 0),
    resolved_by INTEGER REFERENCES users(id), -- admin who resolved
    
    -- Communication
    last_message TEXT,
    message_count INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME,
    escalated_at DATETIME
);

-- Disputes indexes
CREATE INDEX idx_dispute_transaction ON disputes(transaction_id);
CREATE INDEX idx_dispute_channel ON disputes(channel_id);
CREATE INDEX idx_dispute_users ON disputes(initiator_id, respondent_id);
CREATE INDEX idx_dispute_status ON disputes(status);

-- =====================================================
-- 8. ⭐ REVIEWS TABLE - User reviews and ratings
-- =====================================================
CREATE TABLE reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    channel_id INTEGER REFERENCES channels(id),
    
    -- Review parties
    reviewer_id INTEGER NOT NULL REFERENCES users(id),
    reviewed_user_id INTEGER NOT NULL REFERENCES users(id),
    
    -- Review details
    review_type TEXT NOT NULL CHECK(review_type IN ('seller_review', 'buyer_review', 'channel_review')),
    rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
    
    -- Review content
    title TEXT,
    comment TEXT,
    
    -- Review categories
    communication_rating INTEGER CHECK(communication_rating >= 1 AND communication_rating <= 5),
    accuracy_rating INTEGER CHECK(accuracy_rating >= 1 AND accuracy_rating <= 5),
    delivery_rating INTEGER CHECK(delivery_rating >= 1 AND delivery_rating <= 5),
    
    -- Verification
    is_verified_purchase BOOLEAN DEFAULT 1,
    is_visible BOOLEAN DEFAULT 1,
    
    -- Response
    has_response BOOLEAN DEFAULT 0,
    response_text TEXT,
    response_date DATETIME,
    
    -- Moderation
    is_flagged BOOLEAN DEFAULT 0,
    flag_reason TEXT,
    moderated_by INTEGER REFERENCES users(id),
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Reviews indexes
CREATE INDEX idx_review_transaction ON reviews(transaction_id);
CREATE INDEX idx_review_channel ON reviews(channel_id);
CREATE INDEX idx_review_users ON reviews(reviewer_id, reviewed_user_id);
CREATE INDEX idx_review_rating ON reviews(rating);
CREATE INDEX idx_review_type ON reviews(review_type);

-- =====================================================
-- 9. 📊 CHANNEL_ANALYTICS TABLE - Track performance metrics
-- =====================================================
CREATE TABLE channel_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    
    -- Daily metrics
    date DATE NOT NULL,
    
    -- Member metrics
    member_count INTEGER CHECK(member_count >= 0),
    member_growth INTEGER, -- daily change (can be negative)
    active_members INTEGER CHECK(active_members >= 0),
    
    -- Engagement metrics
    messages_sent INTEGER DEFAULT 0,
    media_sent INTEGER DEFAULT 0,
    reactions_count INTEGER DEFAULT 0,
    views_total INTEGER DEFAULT 0,
    shares_count INTEGER DEFAULT 0,
    
    -- Financial metrics
    revenue_generated DECIMAL(20,9) DEFAULT 0, -- if monetized
    tips_received DECIMAL(20,9) DEFAULT 0,
    
    -- Gift metrics
    active_gifts_count INTEGER DEFAULT 0,
    gifts_value_ton DECIMAL(20,9) DEFAULT 0,
    
    -- Quality metrics
    spam_score DECIMAL(3,2) DEFAULT 0 CHECK(spam_score >= 0 AND spam_score <= 1), -- 0-1 scale
    quality_score DECIMAL(3,2) DEFAULT 0 CHECK(quality_score >= 0 AND quality_score <= 10), -- 0-10 scale
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(channel_id, date)
);

-- Channel analytics indexes
CREATE INDEX idx_analytics_channel ON channel_analytics(channel_id);
CREATE INDEX idx_analytics_date ON channel_analytics(date);

-- =====================================================
-- 10. 🔔 NOTIFICATIONS TABLE - User notifications system
-- =====================================================
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Notification details
    type TEXT NOT NULL CHECK(type IN ('new_offer', 'verification_complete', 'payment_received', 'dispute_update', 'channel_sold', 'review_received', 'system_alert')),
    priority TEXT DEFAULT 'normal' CHECK(priority IN ('low', 'normal', 'high', 'urgent')),
    
    -- Content
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    action_url TEXT,
    
    -- Related entities
    channel_id INTEGER REFERENCES channels(id),
    transaction_id INTEGER REFERENCES transactions(id),
    
    -- Status
    is_read BOOLEAN DEFAULT 0,
    is_sent BOOLEAN DEFAULT 0,
    sent_via TEXT CHECK(sent_via IN ('telegram', 'email', 'push', 'sms')),
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    read_at DATETIME,
    sent_at DATETIME,
    expires_at DATETIME
);

-- Notifications indexes
CREATE INDEX idx_notif_user ON notifications(user_id);
CREATE INDEX idx_notif_read ON notifications(is_read);
CREATE INDEX idx_notif_type ON notifications(type);
CREATE INDEX idx_notif_priority ON notifications(priority);

-- =====================================================
-- 11. 🏷️ PRICE_HISTORY TABLE - Track channel price changes
-- =====================================================
CREATE TABLE price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    
    -- Price change
    old_price DECIMAL(20,9),
    new_price DECIMAL(20,9) NOT NULL CHECK(new_price > 0),
    price_change_percent DECIMAL(5,2),
    
    -- Context
    change_reason TEXT CHECK(change_reason IN ('manual', 'negotiated', 'market_adjustment', 'promotion', 'demand_based')),
    changed_by INTEGER REFERENCES users(id),
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Price history indexes
CREATE INDEX idx_price_history_channel ON price_history(channel_id);
CREATE INDEX idx_price_history_date ON price_history(created_at);

-- =====================================================
-- 12. 💼 ESCROW_ACCOUNTS TABLE - Manage secure transactions
-- =====================================================
CREATE TABLE escrow_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER UNIQUE NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    
    -- Escrow details
    escrow_address TEXT UNIQUE NOT NULL, -- dedicated escrow wallet
    amount_locked DECIMAL(20,9) NOT NULL CHECK(amount_locked > 0),
    
    -- Parties
    buyer_id INTEGER NOT NULL REFERENCES users(id),
    seller_id INTEGER NOT NULL REFERENCES users(id),
    
    -- Status
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'released', 'refunded', 'disputed')),
    
    -- Release conditions
    auto_release_days INTEGER DEFAULT 7 CHECK(auto_release_days > 0),
    release_conditions TEXT, -- JSON string with specific conditions for release
    
    -- Release approval
    buyer_approved BOOLEAN DEFAULT 0,
    seller_approved BOOLEAN DEFAULT 0,
    admin_approved BOOLEAN DEFAULT 0,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    locked_at DATETIME,
    released_at DATETIME,
    auto_release_at DATETIME
);

-- Escrow accounts indexes
CREATE INDEX idx_escrow_transaction ON escrow_accounts(transaction_id);
CREATE INDEX idx_escrow_status ON escrow_accounts(status);
CREATE INDEX idx_escrow_parties ON escrow_accounts(buyer_id, seller_id);
CREATE INDEX idx_escrow_auto_release ON escrow_accounts(auto_release_at);

-- =====================================================
-- 13. 🎯 CHANNEL_OFFERS TABLE - Handle negotiation and offers
-- =====================================================
CREATE TABLE channel_offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    
    -- Offer parties
    buyer_id INTEGER NOT NULL REFERENCES users(id),
    seller_id INTEGER NOT NULL REFERENCES users(id),
    
    -- Offer details
    offer_amount DECIMAL(20,9) NOT NULL CHECK(offer_amount > 0),
    original_price DECIMAL(20,9) NOT NULL CHECK(original_price > 0),
    
    -- Status
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'accepted', 'rejected', 'countered', 'expired', 'withdrawn')),
    
    -- Negotiation
    counter_amount DECIMAL(20,9) CHECK(counter_amount > 0),
    counter_count INTEGER DEFAULT 0,
    max_counter_allowed INTEGER DEFAULT 3,
    
    -- Terms
    payment_terms TEXT,
    special_conditions TEXT,
    
    -- Validity
    valid_until DATETIME,
    
    -- Response
    seller_response TEXT,
    buyer_notes TEXT,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    responded_at DATETIME,
    accepted_at DATETIME
);

-- Channel offers indexes
CREATE INDEX idx_offer_channel ON channel_offers(channel_id);
CREATE INDEX idx_offer_buyer ON channel_offers(buyer_id);
CREATE INDEX idx_offer_seller ON channel_offers(seller_id);
CREATE INDEX idx_offer_status ON channel_offers(status);
CREATE INDEX idx_offer_valid_until ON channel_offers(valid_until);

-- =====================================================
-- 14. 🔍 AUDIT_LOGS TABLE - Track all important system actions
-- =====================================================
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Actor
    user_id INTEGER REFERENCES users(id),
    ip_address TEXT,
    user_agent TEXT,
    
    -- Action details
    action TEXT NOT NULL, -- 'channel_listed', 'payment_processed', 'dispute_opened', etc.
    entity_type TEXT CHECK(entity_type IN ('channel', 'transaction', 'user', 'dispute', 'review', 'offer')),
    entity_id INTEGER,
    
    -- Changes
    old_values TEXT, -- JSON string
    new_values TEXT, -- JSON string
    
    -- Context
    description TEXT,
    severity TEXT DEFAULT 'info' CHECK(severity IN ('debug', 'info', 'warning', 'error', 'critical')),
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Audit logs indexes
CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_date ON audit_logs(created_at);
CREATE INDEX idx_audit_severity ON audit_logs(severity);

-- =====================================================
-- 🔧 TRIGGERS - Maintain data integrity and automation
-- =====================================================

-- Update user ratings when reviews are added
CREATE TRIGGER update_user_ratings_after_review
AFTER INSERT ON reviews
BEGIN
    -- Update seller rating
    UPDATE users 
    SET seller_rating = (
        SELECT ROUND(AVG(CAST(rating AS REAL)), 2)
        FROM reviews 
        WHERE reviewed_user_id = NEW.reviewed_user_id 
        AND review_type = 'seller_review'
        AND is_visible = 1
    )
    WHERE id = NEW.reviewed_user_id AND NEW.review_type = 'seller_review';
    
    -- Update buyer rating
    UPDATE users 
    SET buyer_rating = (
        SELECT ROUND(AVG(CAST(rating AS REAL)), 2)
        FROM reviews 
        WHERE reviewed_user_id = NEW.reviewed_user_id 
        AND review_type = 'buyer_review'
        AND is_visible = 1
    )
    WHERE id = NEW.reviewed_user_id AND NEW.review_type = 'buyer_review';
END;

-- Update channel status when sold
CREATE TRIGGER update_channel_status_on_sale
AFTER UPDATE ON transactions
WHEN NEW.status = 'completed' AND NEW.transaction_type = 'channel_purchase'
BEGIN
    UPDATE channels 
    SET status = 'sold', sold_at = CURRENT_TIMESTAMP
    WHERE id = NEW.channel_id;
    
    -- Update user statistics
    UPDATE users 
    SET total_sales = total_sales + 1
    WHERE id = NEW.seller_id;
    
    UPDATE users 
    SET total_purchases = total_purchases + 1
    WHERE id = NEW.buyer_id;
END;

-- Auto-expire offers
CREATE TRIGGER expire_old_offers
AFTER INSERT ON channel_offers
BEGIN
    UPDATE channel_offers 
    SET status = 'expired'
    WHERE valid_until < CURRENT_TIMESTAMP AND status = 'pending';
END;

-- Update timestamps
CREATE TRIGGER update_users_timestamp
AFTER UPDATE ON users
BEGIN
    UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER update_channels_timestamp
AFTER UPDATE ON channels
BEGIN
    UPDATE channels SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER update_disputes_timestamp
AFTER UPDATE ON disputes
BEGIN
    UPDATE disputes SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- =====================================================
-- 🎯 VIEWS - Convenient data access
-- =====================================================

-- Active channels with seller info
CREATE VIEW active_channels_view AS
SELECT 
    c.*,
    u.username as seller_username,
    u.seller_rating,
    u.total_sales,
    COUNT(cg.id) as gifts_count,
    SUM(CASE WHEN cg.is_verified = 1 THEN 1 ELSE 0 END) as verified_gifts_count
FROM channels c
JOIN users u ON c.seller_id = u.id
LEFT JOIN channel_gifts cg ON c.id = cg.channel_id
WHERE c.status = 'active' AND c.visibility = 'public'
GROUP BY c.id;

-- Transaction summary view
CREATE VIEW transaction_summary_view AS
SELECT 
    t.*,
    buyer.username as buyer_username,
    seller.username as seller_username,
    c.channel_title,
    c.channel_username
FROM transactions t
LEFT JOIN users buyer ON t.buyer_id = buyer.id
LEFT JOIN users seller ON t.seller_id = seller.id
LEFT JOIN channels c ON t.channel_id = c.id;

-- User statistics view
CREATE VIEW user_stats_view AS
SELECT 
    u.*,
    COUNT(DISTINCT c.id) as channels_listed,
    COUNT(DISTINCT CASE WHEN c.status = 'sold' THEN c.id END) as channels_sold,
    COUNT(DISTINCT t_buy.id) as purchases_made,
    COUNT(DISTINCT t_sell.id) as sales_made,
    AVG(CASE WHEN r_seller.rating IS NOT NULL THEN r_seller.rating END) as avg_seller_rating,
    AVG(CASE WHEN r_buyer.rating IS NOT NULL THEN r_buyer.rating END) as avg_buyer_rating
FROM users u
LEFT JOIN channels c ON u.id = c.seller_id
LEFT JOIN transactions t_buy ON u.id = t_buy.buyer_id AND t_buy.transaction_type = 'channel_purchase'
LEFT JOIN transactions t_sell ON u.id = t_sell.seller_id AND t_sell.transaction_type = 'channel_purchase'
LEFT JOIN reviews r_seller ON u.id = r_seller.reviewed_user_id AND r_seller.review_type = 'seller_review'
LEFT JOIN reviews r_buyer ON u.id = r_buyer.reviewed_user_id AND r_buyer.review_type = 'buyer_review'
GROUP BY u.id;

-- =====================================================
-- 🏁 SCHEMA COMPLETE
-- =====================================================

-- Insert initial admin user (optional)
INSERT OR IGNORE INTO users (
    telegram_id, 
    username, 
    full_name, 
    main_wallet_address, 
    user_type, 
    verification_status,
    is_active
) VALUES (
    'admin_001', 
    'marketplace_admin', 
    'Marketplace Administrator', 
    'ADMIN_WALLET_ADDRESS_PLACEHOLDER', 
    'admin', 
    'verified',
    1
);

-- Schema creation completed successfully!
-- Total tables: 14
-- Total indexes: 50+
-- Total triggers: 6
-- Total views: 3
