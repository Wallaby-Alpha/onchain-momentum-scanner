import html
import logging
import requests
from typing import Dict, Any, List
from src.config import Config

logger = logging.getLogger(__name__)

CHAIN_EMOJIS = {
    "solana": "🟣 Solana",
    "base": "🔵 Base",
    "ethereum": "🔷 Ethereum",
    "bsc": "🟡 BSC",
    "arbitrum": "🔷 Arbitrum"
}


def format_token_alert(rank: int, token: Dict[str, Any]) -> str:
    """
    Format a scored token into a clean, modern Telegram HTML alert message.
    """
    raw_symbol = token.get("symbol", "UNKNOWN")
    raw_name = token.get("name", "")
    symbol = html.escape(str(raw_symbol))
    name = html.escape(str(raw_name))

    chain = token.get("chain_id", "").lower()
    chain_label = CHAIN_EMOJIS.get(chain, chain.capitalize())
    
    score = token.get("momentum_score", 0.0)
    price = token.get("price_usd", 0.0)
    mcap = token.get("market_cap", 0.0)
    liq = token.get("liquidity_usd", 0.0)
    vol_24h = token.get("volume_24h", 0.0)
    
    pc_1h = token.get("price_change_1h", 0.0)
    pc_6h = token.get("price_change_6h", 0.0)
    pc_24h = token.get("price_change_24h", 0.0)
    
    pc_1h_str = f"+{pc_1h:.1f}%" if pc_1h >= 0 else f"{pc_1h:.1f}%"
    pc_6h_str = f"+{pc_6h:.1f}%" if pc_6h >= 0 else f"{pc_6h:.1f}%"
    pc_24h_str = f"+{pc_24h:.1f}%" if pc_24h >= 0 else f"{pc_24h:.1f}%"

    buys_1h = token.get("txns_1h_buys", 0)
    sells_1h = token.get("txns_1h_sells", 0)
    buyer_ratio = token.get("buyer_ratio_1h", 0.5) * 100.0
    vol_accel = token.get("volume_accel_1h", 1.0)
    age_days = token.get("age_days", 0.0)
    
    dex_url = token.get("dex_url", "")
    token_addr = token.get("token_address", "")

    # Format price with appropriate decimals
    if price >= 1.0:
        price_str = f"${price:,.2f}"
    elif price >= 0.001:
        price_str = f"${price:.4f}"
    else:
        price_str = f"${price:.8f}"

    msg = f"""🔥 <b>ON-CHAIN MOMENTUM LEADER #{rank}</b>

🪙 <b>{symbol}</b> ({name})
⛓ <b>Network:</b> {chain_label}
📈 <b>Momentum Score:</b> <code>{score}/100</code>

💰 <b>Price:</b> {price_str}
🏛 <b>Market Cap:</b> ${mcap:,.0f}
💧 <b>Liquidity:</b> ${liq:,.0f}
📊 <b>24h Volume:</b> ${vol_24h:,.0f}

⏱ <b>Multi-Timeframe Trend:</b>
• 1h: <b>{pc_1h_str}</b>
• 6h: <b>{pc_6h_str}</b>
• 24h: <b>{pc_24h_str}</b>

🎯 <b>Order Flow & Activity:</b>
• 1h Buys / Sells: <code>{buys_1h}</code> / <code>{sells_1h}</code> (<b>{buyer_ratio:.0f}%</b> Buyers)
• Volume Run-Rate: <b>{vol_accel:.1f}x</b> normal hourly pace
• Token Age: <b>{age_days:.1f} days</b>

🔗 <a href="{dex_url}">View on DexScreener</a> | <code>{token_addr}</code>
"""
    return msg.strip()


def send_telegram_message(html_text: str) -> bool:
    """Send an HTML message via Telegram Bot API."""
    if not Config.ENABLE_TELEGRAM:
        logger.info("[Telegram Disabled] Outputting alert to log:")
        print(html_text)
        return True

    if not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHAT_ID:
        logger.warning("Telegram Bot Token or Chat ID not configured. Printing alert to console.")
        print("\n" + "="*50)
        print(html_text)
        print("="*50 + "\n")
        return False

    url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": Config.TELEGRAM_CHAT_ID,
        "text": html_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            logger.info("Successfully dispatched Telegram alert.")
            return True
        else:
            logger.error(f"Telegram dispatch failed: {res.status_code} - {res.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram dispatch exception: {e}")
        return False


def send_scan_summary(leaders: List[Dict[str, Any]]):
    """
    Dispatches alerts for the top momentum leaders.
    """
    if not leaders:
        return

    for rank, token in enumerate(leaders, 1):
        alert_msg = format_token_alert(rank, token)
        send_telegram_message(alert_msg)


def test_telegram_connection():
    """
    Self-diagnostic script to verify Telegram credentials and permissions.
    """
    print("\n" + "="*60)
    print("🔍 TELEGRAM CONNECTION DIAGNOSTIC")
    print("="*60)

    token = Config.TELEGRAM_BOT_TOKEN
    chat_id = Config.TELEGRAM_CHAT_ID

    print(f"• ENABLE_TELEGRAM: {Config.ENABLE_TELEGRAM}")
    masked_token = f"{token[:8]}...{token[-4:]}" if len(token) > 12 else (token or "(NOT SET)")
    print(f"• TELEGRAM_BOT_TOKEN: {masked_token}")
    print(f"• TELEGRAM_CHAT_ID: {chat_id or '(NOT SET)'}")

    if not token or not chat_id:
        print("\n❌ ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing!")
        print("   Make sure your .env file in the project directory defines both:")
        print("   TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWxyz")
        print("   TELEGRAM_CHAT_ID=123456789 (or @yourchannel)")
        return False

    # 1. Validate Bot Token via getMe
    print("\n1. Testing Bot Token validity with Telegram getMe API...")
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        if r.status_code == 200:
            bot_info = r.json().get("result", {})
            print(f"   ✅ Token is valid! Bot username: @{bot_info.get('username')} ({bot_info.get('first_name')})")
        else:
            print(f"   ❌ Telegram getMe failed: {r.status_code} - {r.text}")
            print("   Please check that TELEGRAM_BOT_TOKEN was copied correctly from @BotFather.")
            return False
    except Exception as e:
        print(f"   ❌ Connection error reaching api.telegram.org: {e}")
        return False

    # 2. Test sending a message to Chat ID
    print(f"\n2. Attempting to send test message to Chat ID '{chat_id}'...")
    test_text = (
        "<b>🤖 On-Chain Momentum Scanner Test Alert</b>\n\n"
        "✅ Your Telegram bot integration is working properly!\n"
        "Live alerts will appear in this format."
    )
    success = send_telegram_message(test_text)
    if success:
        print("   🎉 SUCCESS! Test alert was delivered to Telegram.")
    else:
        print("   ❌ Failed to deliver message. Check the error message above.")
        print("\nCommon fixes:")
        print("   • If sending to your personal account: Did you press '/start' in the bot first?")
        print("   • If sending to a channel or group: Did you add the bot as an Administrator with 'Post Messages' permission?")
        print("   • If using a channel username, did you prefix it with '@' (e.g., @mychannel) or use the numeric ID (e.g., -100...)?")
    return success


if __name__ == "__main__":
    test_telegram_connection()
