import os
import discord
from dotenv import load_dotenv
from db import init_db, add_user, get_user, add_commit, log_hours, get_recent_logs
from github_utils import validate_github_user, get_recent_commits
from datetime import datetime, timedelta
import asyncio
import logging
from utils.security import (
    InputValidator, SecurityUtils, bot_command_rate_limiter
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Bot module loaded")

# Ładowanie zmiennych
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID', '0'))
OAUTH_REDIRECT_URI = os.getenv('OAUTH_REDIRECT_URI')

# Validate required environment variables
if not TOKEN:
    raise RuntimeError('DISCORD_TOKEN environment variable is not set')
if not GITHUB_TOKEN:
    raise RuntimeError('GITHUB_TOKEN environment variable is not set')
if not OAUTH_REDIRECT_URI:
    raise RuntimeError('OAUTH_REDIRECT_URI environment variable is not set')

# Ensure OAUTH_REDIRECT_URI does not end with '/callback'
if OAUTH_REDIRECT_URI.endswith('/callback'):
    OAUTH_REDIRECT_URI = OAUTH_REDIRECT_URI[:-9]

# Inicjalizacja bazy danych
init_db()

# Konfiguracja bota
intents = discord.Intents.default()
bot = discord.Bot(intents=intents)

# Manual cooldown tracking for /log command (in addition to rate limiting)
user_cooldowns = {}

@bot.event
async def on_ready():
    logger.info(f'Bot logged in as {bot.user}')
    print(f'Bot is ready! Logged in as {bot.user}')

@bot.slash_command(description='Get link to link your GitHub account')
async def link(ctx: discord.ApplicationContext):
    """Get a link to connect your GitHub account via OAuth."""
    try:
        # Rate limiting
        is_allowed, retry_after = bot_command_rate_limiter.is_allowed(str(ctx.author.id))
        if not is_allowed:
            await ctx.respond(
                f'Rate limit exceeded. Please try again in {retry_after:.0f} seconds.',
                ephemeral=True
            )
            return
        # Validate Discord ID
        discord_id = str(ctx.author.id)
        if not InputValidator.validate_discord_id(discord_id):
            logger.warning(f"Invalid Discord ID in link command: {SecurityUtils.hash_sensitive_data(discord_id)}")
            await ctx.respond('Invalid Discord ID.', ephemeral=True)
            return
        url = f"{OAUTH_REDIRECT_URI}/oauth/start?discord_id={discord_id}"
        await ctx.respond(f'Click to link your GitHub: {url}', ephemeral=True)
        logger.info(f"User {SecurityUtils.hash_sensitive_data(discord_id)} requested GitHub link")
    except Exception as e:
        logger.error(f"Error in link command: {e}")
        await ctx.respond('An error occurred while generating the link.', ephemeral=True)

@bot.slash_command(description='Log volunteer hours for last GitHub push')
async def log(ctx: discord.ApplicationContext, hours: float):
    """Log volunteer hours for a recent GitHub commit."""
    try:
        # Rate limiting
        is_allowed, retry_after = bot_command_rate_limiter.is_allowed(str(ctx.author.id))
        if not is_allowed:
            await ctx.respond(
                f'⏳ Rate limit exceeded. Please try again in {retry_after:.0f} seconds.',
                ephemeral=True
            )
            return
        # Validate hours input
        if not InputValidator.validate_hours(hours):
            await ctx.respond('Hours must be between 0 and 24.', ephemeral=True)
            return
        # Manual cooldown (10s per user)
        now = datetime.utcnow()
        last_used = user_cooldowns.get(ctx.author.id)
        if last_used and (now - last_used).total_seconds() < 10:
            retry_after = 10 - (now - last_used).total_seconds()
            await ctx.respond(
                f'⏳ Please wait {retry_after:.1f}s before using this command again.',
                ephemeral=True
            )
            return
        user_cooldowns[ctx.author.id] = now
        # Validate Discord ID
        discord_id = str(ctx.author.id)
        if not InputValidator.validate_discord_id(discord_id):
            logger.warning(f"Invalid Discord ID in log command: {SecurityUtils.hash_sensitive_data(discord_id)}")
            await ctx.respond('Invalid Discord ID.', ephemeral=True)
            return
        # Check if user is linked
        user = get_user(discord_id)
        if not user:
            await ctx.respond('You must link your GitHub first: `/link`', ephemeral=True)
            return
        # Validate GitHub username
        if not InputValidator.validate_github_username(user['github_login']):
            logger.warning(f"Invalid GitHub username in database: {user['github_login']}")
            await ctx.respond('Invalid GitHub username in database.', ephemeral=True)
            return
        logger.info(f"User {SecurityUtils.hash_sensitive_data(discord_id)} ({user['github_login']}) logging {hours}h")
        # Get recent commits
        since = (datetime.utcnow() - timedelta(days=7)).isoformat()
        if not isinstance(GITHUB_TOKEN, str) or not GITHUB_TOKEN:
            await ctx.respond('Internal error: GitHub token is not set.', ephemeral=True)
            logger.error("GITHUB_TOKEN is not set or not a string")
            return
        if not (isinstance(user, dict) and 'github_login' in user):
            await ctx.respond('Internal error: User data is invalid.', ephemeral=True)
            logger.error(f"User object is not a dict: {user}")
            return
        commits = get_recent_commits(user['github_login'], GITHUB_TOKEN, since)
        if not commits:
            await ctx.respond('No GitHub commits found in the last 7 days.', ephemeral=True)
            return
        # Create select menu options with validation
        options = []
        for commit in commits[:25]:  # Limit to 25 options (Discord limit)
            # Validate commit SHA
            if not InputValidator.validate_commit_sha(commit['id']):
                logger.warning(f"Invalid commit SHA: {commit['id']}")
                continue
            # Sanitize commit message
            message = InputValidator.sanitize_string(commit['message'], 50)
            label = message.strip().replace('\n', ' ')
            if len(label) == 50:
                label += "..."
            options.append(
                discord.SelectOption(
                    label=label,
                    value=commit['id'],
                    description=f"Repo: {commit.get('repo', 'unknown')} • {commit['date'][:10]}"
                )
            )
        if not options:
            await ctx.respond('No valid commits found to log hours for.', ephemeral=True)
            return
        select = discord.ui.Select(placeholder='Choose a commit', options=options)
        async def callback(interaction: discord.Interaction):
            try:
                commit_id = str(select.values[0])
                # Validate commit ID again
                if not InputValidator.validate_commit_sha(commit_id):
                    await interaction.response.send_message('Invalid commit ID.', ephemeral=True)
                    return
                log_hours(discord_id, commit_id, hours)
                await interaction.response.send_message(
                    f'Logged {hours}h for commit `{commit_id[:7]}`', ephemeral=True
                )
                logger.info(f"User {SecurityUtils.hash_sensitive_data(discord_id)} logged {hours}h for commit {commit_id[:7]}")
            except Exception as e:
                logger.error(f"Error in log callback: {e}")
                await interaction.response.send_message('An error occurred while logging hours.', ephemeral=True)
        select.callback = callback
        view = discord.ui.View(timeout=60)
        view.add_item(select)
        await ctx.respond(f'Select a commit to log {hours}h for:', view=view, ephemeral=True)
    except Exception as e:
        logger.error(f"Error in log command: {e}")
        await ctx.respond('An error occurred while processing your request.', ephemeral=True)

@bot.slash_command(description='Show your recent logs')
async def history(ctx: discord.ApplicationContext, limit: int = 5):
    """Show your recent volunteer hour logs."""
    try:
        # Rate limiting
        is_allowed, retry_after = bot_command_rate_limiter.is_allowed(str(ctx.author.id))
        if not is_allowed:
            await ctx.respond(
                f'Rate limit exceeded. Please try again in {retry_after:.0f} seconds.',
                ephemeral=True
            )
            return
        # Validate limit
        if not InputValidator.validate_limit(limit):
            await ctx.respond('Limit must be between 1 and 100.', ephemeral=True)
            return
        # Validate Discord ID
        discord_id = str(ctx.author.id)
        if not InputValidator.validate_discord_id(discord_id):
            logger.warning(f"Invalid Discord ID in history command: {SecurityUtils.hash_sensitive_data(discord_id)}")
            await ctx.respond('Invalid Discord ID.', ephemeral=True)
            return
        rows = get_recent_logs(discord_id, limit)
        if not rows:
            await ctx.respond('No logs found.', ephemeral=True)
            return
        # Format the message with validation
        msg_lines = []
        total_hours = 0
        for commit_id, hours, logged_at in rows:
            # Validate data
            if not InputValidator.validate_commit_sha(commit_id):
                logger.warning(f"Invalid commit SHA in history: {commit_id}")
                continue
            if not InputValidator.validate_hours(hours):
                logger.warning(f"Invalid hours in history: {hours}")
                continue
            total_hours += hours
            date_str = logged_at[:19] if logged_at else "Unknown"
            msg_lines.append(f"`{commit_id[:7]}`: {hours}h at {date_str}")
        if not msg_lines:
            await ctx.respond('No valid logs found.', ephemeral=True)
            return
        msg = '\n'.join(msg_lines)
        await ctx.respond(f'Your recent logs (Total: {total_hours}h):\n{msg}', ephemeral=True)
        logger.info(f"User {SecurityUtils.hash_sensitive_data(discord_id)} viewed {len(rows)} logs")
    except Exception as e:
        logger.error(f"Error in history command: {e}")
        await ctx.respond('An error occurred while fetching your history.', ephemeral=True)

@bot.slash_command(description='Check your GitHub account status')
async def status(ctx: discord.ApplicationContext):
    """Check if your GitHub account is linked and get basic info."""
    try:
        # Rate limiting
        is_allowed, retry_after = bot_command_rate_limiter.is_allowed(str(ctx.author.id))
        if not is_allowed:
            await ctx.respond(
                f'Rate limit exceeded. Please try again in {retry_after:.0f} seconds.',
                ephemeral=True
            )
            return
        # Validate Discord ID
        discord_id = str(ctx.author.id)
        if not InputValidator.validate_discord_id(discord_id):
            logger.warning(f"Invalid Discord ID in status command: {SecurityUtils.hash_sensitive_data(discord_id)}")
            await ctx.respond('Invalid Discord ID.', ephemeral=True)
            return
        user = get_user(discord_id)
        if not user:
            await ctx.respond('Your GitHub account is not linked. Use `/link` to connect.', ephemeral=True)
            return
        # Validate GitHub username
        if not InputValidator.validate_github_username(user['github_login']):
            logger.warning(f"Invalid GitHub username in status: {user['github_login']}")
            await ctx.respond('Invalid GitHub username in database.', ephemeral=True)
            return
        # Get recent commits count
        since = (datetime.utcnow() - timedelta(days=7)).isoformat()
        if not isinstance(GITHUB_TOKEN, str) or not GITHUB_TOKEN:
            await ctx.respond('Internal error: GitHub token is not set.', ephemeral=True)
            logger.error("GITHUB_TOKEN is not set or not a string")
            return
        commits = get_recent_commits(user['github_login'], GITHUB_TOKEN, since)
        embed = discord.Embed(
            title="GitHub Account Status",
            color=discord.Color.green()
        )
        embed.add_field(name="GitHub Username", value=user['github_login'], inline=True)
        embed.add_field(name="Linked Since", value=user['validated_at'][:19], inline=True)
        embed.add_field(name="Recent Commits (7 days)", value=str(len(commits)), inline=True)
        await ctx.respond(embed=embed, ephemeral=True)
        logger.info(f"User {SecurityUtils.hash_sensitive_data(discord_id)} checked status")
    except Exception as e:
        logger.error(f"Error in status command: {e}")
        await ctx.respond('An error occurred while checking your status.', ephemeral=True)

#Odpal buster bot
if __name__ == "__main__":
    bot.run(TOKEN)