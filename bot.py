import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from db import init_db, add_user, get_user, add_commit, log_hours, get_recent_logs
from github_utils import validate_github_user, get_recent_commits
from datetime import datetime, timedelta

# Ładowanie zmiennych
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID', '0'))
OAUTH_REDIRECT_URI = os.getenv('OAUTH_REDIRECT_URI')

# Inicjalizacja bazy danych
init_db()

# Konfiguracja bota
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='/', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot logged in as {bot.user}')

@bot.slash_command(description='Get link to link your GitHub account')
async def link(ctx: discord.ApplicationContext):
    url = f"{OAUTH_REDIRECT_URI}/oauth/start?discord_id={ctx.author.id}"
    await ctx.respond(f'🔗 Click to link your GitHub: {url}', ephemeral=True)

@bot.slash_command(description='Log volunteer hours for last GitHub push')
@commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
async def log(ctx: discord.ApplicationContext, hours: float):
    user = get_user(str(ctx.author.id))
    if not user:
        await ctx.respond('You must link your GitHub first: /link', ephemeral=True)
        return

    since = (datetime.utcnow() - timedelta(days=7)).isoformat()
    commits = get_recent_commits(user['github_login'], GITHUB_TOKEN, since)

    if not commits:
        await ctx.respond('No GitHub commits found in the last 7 days.', ephemeral=True)
        return

    options = [
        discord.SelectOption(
            label=c['message'].strip().replace('\n', ' ')[:50],
            value=c['id']
        ) for c in commits
    ]

    select = discord.ui.Select(placeholder='Choose a commit', options=options)

    async def callback(interaction: discord.Interaction):
        commit_id = select.values[0]
        log_hours(str(ctx.author.id), commit_id, hours)
        await interaction.response.send_message(
            f'Logged {hours}h for commit `{commit_id[:7]}`', ephemeral=True
        )

    select.callback = callback
    view = discord.ui.View(timeout=60)
    view.add_item(select)

    await ctx.respond('Select commit to log hours for:', view=view, ephemeral=True)

@log.error
async def log_error(ctx: discord.ApplicationContext, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.respond(
            f'⏳ Please wait {error.retry_after:.1f}s before using this command again.',
            ephemeral=True
        )
    else:
        await ctx.respond('An error occurred while processing your request.', ephemeral=True)

@bot.slash_command(description='Show your recent logs')
async def history(ctx: discord.ApplicationContext, limit: int = 5):
    rows = get_recent_logs(str(ctx.author.id), limit)

    if not rows:
        await ctx.respond('No logs found.', ephemeral=True)
        return

    msg = '\n'.join([
        f"`{commit_id[:7]}`: {hours}h at {logged_at}" for commit_id, hours, logged_at in rows
    ])

    await ctx.respond(f'Your recent logs:\n{msg}', ephemeral=True)

#Odpal buster bot
bot.run(TOKEN)
