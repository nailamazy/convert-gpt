"""
Telegram Bot - ChatGPT Checkout Link Converter
Converts chatgpt.com/checkout links to pay.openai.com/c/pay links
"""

import os
import re
import base64
import urllib.parse
import json
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ============================================================
# CONFIGURATION
# ============================================================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# OpenAI's Stripe publishable key and checkout config
OPENAI_STRIPE_CONFIG = {
    "borderStyle": "default",
    "locale": "en",
    "subscriptionUniquenessEnabled": False,
    "apiKey": "pk_live_51HOrSwC6h1nxGoI3lTAgRjYVrz4dU3fVOabyCcKR3pbEJguCVAlqCxdxCUvoRh1XWwRacViovU3kLKvpkjh7IqkW00iXQsjo3n",
    "fromServer": True,
    "backdkoundColor": "#ffffff",
    "layoutType": "single_item",
    "enablePlaceholders": True
}

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ============================================================
# STRIPE ENCODING FUNCTIONS
# ============================================================
def stripe_xor_encode(plain_text: str) -> str:
    """XOR each character with 5 (Stripe's encoding)"""
    return ''.join(chr(5 ^ ord(c)) for c in plain_text)


def stripe_encode_fragment(config: dict) -> str:
    """
    Encode a JSON config dict into Stripe's URL fragment format.
    Process: JSON string -> XOR with 5 -> pad to multiple of 3 -> base64 -> URL encode
    """
    json_str = json.dumps(config, separators=(',', ':'))
    
    # Pad to make length multiple of 3
    remainder = len(json_str) % 3
    if remainder:
        json_str += ' ' * (3 - remainder)
    
    # XOR encode
    xored = stripe_xor_encode(json_str)
    
    # Base64 encode
    b64 = base64.b64encode(xored.encode('latin-1')).decode()
    
    # URL encode (safe='' to encode '/' as %2F like Stripe does)
    return urllib.parse.quote(b64, safe='')


def stripe_decode_fragment(encoded: str) -> str:
    """Decode Stripe's URL fragment back to JSON string"""
    decoded_uri = urllib.parse.unquote(encoded)
    decoded_b64 = base64.b64decode(decoded_uri).decode('latin-1')
    result = ''.join(chr(5 ^ ord(c)) for c in decoded_b64)
    return result.strip()


# ============================================================
# URL CONVERSION
# ============================================================
# Regex to match ChatGPT checkout URLs
CHATGPT_CHECKOUT_PATTERN = re.compile(
    r'https?://chatgpt\.com/checkout/openai_llc/(cs_(?:live|test)_[A-Za-z0-9]+)'
)

# Pre-encode the fragment once
ENCODED_FRAGMENT = stripe_encode_fragment(OPENAI_STRIPE_CONFIG)


def convert_checkout_url(chatgpt_url: str) -> str | None:
    """
    Convert a ChatGPT checkout URL to a Stripe pay.openai.com URL.
    
    Input:  https://chatgpt.com/checkout/openai_llc/cs_live_xxxxx
    Output: https://pay.openai.com/c/pay/cs_live_xxxxx#encoded_fragment
    """
    match = CHATGPT_CHECKOUT_PATTERN.search(chatgpt_url)
    if not match:
        return None
    
    session_id = match.group(1)
    return f"https://pay.openai.com/c/pay/{session_id}#{ENCODED_FRAGMENT}"


def extract_all_links(text: str) -> list[tuple[str, str]]:
    """Extract all ChatGPT checkout URLs from text and return (original, converted) pairs."""
    results = []
    for match in CHATGPT_CHECKOUT_PATTERN.finditer(text):
        original_url = match.group(0)
        converted = convert_checkout_url(original_url)
        if converted:
            results.append((original_url, converted))
    return results


# ============================================================
# TELEGRAM BOT HANDLERS
# ============================================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    welcome_text = (
        "🔄 <b>ChatGPT Checkout Link Converter</b>\n\n"
        "Kirim link checkout ChatGPT dan bot akan mengconvert-nya "
        "ke link pembayaran Stripe langsung.\n\n"
        "<b>Format yang didukung:</b>\n"
        "<code>https://chatgpt.com/checkout/openai_llc/cs_live_xxx</code>\n\n"
        "📌 Cukup kirim link atau pesan yang mengandung link checkout."
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = (
        "ℹ️ <b>Cara Penggunaan</b>\n\n"
        "1️⃣ Kirim link checkout ChatGPT\n"
        "2️⃣ Bot akan otomatis mendeteksi dan mengconvert link\n"
        "3️⃣ Hasilnya adalah link Stripe pay.openai.com\n\n"
        "<b>Contoh Input:</b>\n"
        "<code>https://chatgpt.com/checkout/openai_llc/cs_live_a1sEsORezHbPtqneMQw14bnCVJqsEAG7iYi3MHby9p4odEoUAvcS0jc548</code>\n\n"
        "<b>Commands:</b>\n"
        "/start - Mulai bot\n"
        "/help - Tampilkan bantuan\n"
        "/convert &lt;link&gt; - Convert link secara manual"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")


async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /convert command"""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Gunakan: <code>/convert &lt;link_checkout&gt;</code>",
            parse_mode="HTML"
        )
        return
    
    url = context.args[0]
    converted = convert_checkout_url(url)
    
    if converted:
        response = (
            f"✅ <b>Link Berhasil Diconvert!</b>\n\n"
            f"📥 <b>Original:</b>\n<code>{url}</code>\n\n"
            f"📤 <b>Converted:</b>\n<code>{converted}</code>\n\n"
            f"💡 <i>Tap link di atas untuk copy</i>"
        )
        await update.message.reply_text(response, parse_mode="HTML")
    else:
        response = (
            "❌ <b>Link tidak valid!</b>\n\n"
            "Pastikan format link seperti ini:\n"
            "<code>https://chatgpt.com/checkout/openai_llc/cs_live_xxx</code>"
        )
        await update.message.reply_text(response, parse_mode="HTML")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages and auto-detect checkout links"""
    text = update.message.text
    if not text:
        return
    
    links = extract_all_links(text)
    
    if not links:
        # No checkout links found, ignore silently
        return
    
    for original, converted in links:
        response = (
            f"✅ <b>Link Converted!</b>\n\n"
            f"📤 <b>Stripe Payment Link:</b>\n<code>{converted}</code>\n\n"
            f"💡 <i>Tap link di atas untuk copy</i>"
        )
        await update.message.reply_text(response, parse_mode="HTML")




# ============================================================
# MAIN
# ============================================================
def main():
    """Start the bot"""
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("=" * 60)
        print("ERROR: Set BOT_TOKEN di file .env!")
        print("Dapatkan token dari @BotFather di Telegram")
        print("=" * 60)
        
        # Demo mode - test conversion di terminal
        print("\n--- DEMO MODE (tanpa Telegram) ---\n")
        
        test_urls = [
            "https://chatgpt.com/checkout/openai_llc/cs_live_a1sEsORezHbPtqneMQw14bnCVJqsEAG7iYi3MHby9p4odEoUAvcS0jc548",
            "https://chatgpt.com/checkout/openai_llc/cs_live_a1T03HbG9U60znefs8M6r68saGOtTcinGPTdyc8DM2xnMyJysJnWZVQhVc",
        ]
        
        for url in test_urls:
            converted = convert_checkout_url(url)
            print(f"INPUT:  {url}")
            print(f"OUTPUT: {converted}")
            print()
        
        return
    
    # Build application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("convert", convert_command))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start polling
    logger.info("Bot started! Listening for messages...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
