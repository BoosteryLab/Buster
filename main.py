import os
import sys
import threading
import time
import logging
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

load_dotenv()

def run_discord_bot():
    import asyncio
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Starting Discord bot...")

    # Create and set a new event loop for this thread BEFORE importing bot
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        import bot
        logger.info("Successfully imported bot module")
        # Start the bot (this will block)
        bot.bot.run(bot.TOKEN)
    except Exception as e:
        logger.error(f"Discord bot error: {e}")
        import traceback
        traceback.print_exc()

def check_environment():
    required_vars = [
        'DISCORD_TOKEN', 'GITHUB_CLIENT_ID', 'GITHUB_CLIENT_SECRET', 'GITHUB_TOKEN', 'OAUTH_REDIRECT_URI'
    ]
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
            logger.error(f"Missing environment variable: {var}")
        else:
            masked = value[:8] + "..." if len(value) > 8 else "***"
            logger.info(f"{var}: {masked}")
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return False
    return True

def main():
    logger.info("=" * 50)
    logger.info("Starting Discord Volunteer Tracker Bot...")
    logger.info("=" * 50)

    if not check_environment():
        logger.error("Environment check failed. Exiting.")
        sys.exit(1)

    # Start Discord bot in a background thread
    bot_thread = threading.Thread(target=run_discord_bot, daemon=True)
    bot_thread.start()
    logger.info("Discord bot thread started")

    # Now run aiohttp in the main thread
    try:
        import oauth_server
        import aiohttp.web
        port = int(os.environ.get("PORT", 8000))
        logger.info(f"Starting OAuth server on port {port}")
        aiohttp.web.run_app(oauth_server.app, port=port, host='0.0.0.0')
    except Exception as e:
        logger.error(f"OAuth server error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()