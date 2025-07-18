import os
import secrets
import sqlite3
import requests
from aiohttp import web
from dotenv import load_dotenv
from urllib.parse import urlencode
import logging
from utils.security import (
    RateLimiter, InputValidator, SecurityUtils, 
    oauth_rate_limiter
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("OAuth server module loaded")

load_dotenv()
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET')
OAUTH_REDIRECT_URI = os.getenv('OAUTH_REDIRECT_URI')

# Validate required environment variables
if not OAUTH_REDIRECT_URI:
    raise RuntimeError('OAUTH_REDIRECT_URI environment variable is not set. Please set it in your .env file.')
if not GITHUB_CLIENT_ID:
    raise RuntimeError('GITHUB_CLIENT_ID environment variable is not set. Please set it in your .env file.')
if not GITHUB_CLIENT_SECRET:
    raise RuntimeError('GITHUB_CLIENT_SECRET environment variable is not set. Please set it in your .env file.')

# DB - Use secure connection
conn = sqlite3.connect('volunteer.db', timeout=30.0)
cur = conn.cursor()
routes = web.RouteTableDef()

@routes.get('/oauth/start')
async def oauth_start(request):
    """Start OAuth flow with security validation."""
    try:
        # Get and validate Discord ID
        discord_id = request.query.get('discord_id')
        if not discord_id or not InputValidator.validate_discord_id(discord_id):
            logger.warning(f"Invalid Discord ID in OAuth start: {SecurityUtils.hash_sensitive_data(discord_id or 'None')}")
            return web.Response(text='Invalid Discord ID', status=400)
        
        # Rate limiting
        is_allowed, retry_after = oauth_rate_limiter.is_allowed(discord_id)
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for Discord ID: {SecurityUtils.hash_sensitive_data(discord_id)}")
            return web.Response(
                text=f'Rate limit exceeded. Please try again in {retry_after:.0f} seconds.',
                status=429
            )
        
        # Generate secure state token
        state = SecurityUtils.generate_secure_state()
        
        # Store state in database
        cur.execute(
            'INSERT INTO oauth_states(state, discord_id, created_at) VALUES (?, ?, datetime("now"))', 
            (state, discord_id)
        )
        conn.commit()
        
        # Build OAuth URL
        if not isinstance(OAUTH_REDIRECT_URI, str) or not OAUTH_REDIRECT_URI:
            logger.error("OAUTH_REDIRECT_URI is not set or not a string")
            return web.Response(text='Internal error: OAUTH_REDIRECT_URI is not set', status=500)
        redirect_uri = OAUTH_REDIRECT_URI + '/oauth/callback'
        params = {
            'client_id': GITHUB_CLIENT_ID,
            'redirect_uri': redirect_uri,
            'state': state,
            'scope': 'read:user'
        }
        url = 'https://github.com/login/oauth/authorize?' + urlencode(params)
        
        logger.info(f"OAuth started for Discord ID: {SecurityUtils.hash_sensitive_data(discord_id)}")
        logger.info(f"Redirecting to GitHub OAuth URL: {url}")
        raise web.HTTPFound(url)
        
    except web.HTTPFound as redirect:
        raise redirect
    except Exception as e:
        logger.error(f"Error in OAuth start: {e}")
        return web.Response(text='Internal server error', status=500)

@routes.get('/oauth/callback')
async def oauth_callback(request):
    """Handle OAuth callback with comprehensive security."""
    try:
        # Get and validate parameters
        code = request.query.get('code')
        state = request.query.get('state')
        
        if not code or not state:
            logger.warning("Missing code or state in OAuth callback")
            return web.Response(text='Missing required parameters', status=400)
        
        # Validate state format
        if not SecurityUtils.validate_oauth_state(state):
            logger.warning(f"Invalid state format: {SecurityUtils.hash_sensitive_data(state)}")
            return web.Response(text='Invalid state parameter', status=400)
        
        logger.info(f"OAuth callback received - code: {SecurityUtils.hash_sensitive_data(code)}, state: {SecurityUtils.hash_sensitive_data(state)}")
        
        # Get Discord ID from state
        row = cur.execute('SELECT discord_id FROM oauth_states WHERE state=?', (state,)).fetchone()
        if not row:
            logger.warning(f"Invalid state: {SecurityUtils.hash_sensitive_data(state)}")
            return web.Response(text='Invalid or expired state', status=400)
        
        discord_id = row[0]
        
        # Validate Discord ID
        if not InputValidator.validate_discord_id(discord_id):
            logger.warning(f"Invalid Discord ID from state: {SecurityUtils.hash_sensitive_data(discord_id)}")
            return web.Response(text='Invalid Discord ID', status=400)
        
        logger.info(f"Found discord_id: {SecurityUtils.hash_sensitive_data(discord_id)}")
        
        # Exchange code for access token
        if not isinstance(OAUTH_REDIRECT_URI, str) or not OAUTH_REDIRECT_URI:
            logger.error("OAUTH_REDIRECT_URI is not set or not a string")
            return web.Response(text='Internal error: OAUTH_REDIRECT_URI is not set', status=500)
        redirect_uri = OAUTH_REDIRECT_URI + '/oauth/callback'
        token_res = requests.post(
            'https://github.com/login/oauth/access_token',
            data={
                'client_id': GITHUB_CLIENT_ID,
                'client_secret': GITHUB_CLIENT_SECRET,
                'code': code,
                'redirect_uri': redirect_uri
            },
            headers={'Accept': 'application/json'},
            timeout=30
        )
        
        logger.info(f"Token response status: {token_res.status_code}")
        
        if token_res.status_code != 200:
            logger.error(f"GitHub token exchange failed: {token_res.status_code}")
            return web.Response(text='Failed to authenticate with GitHub', status=400)
        
        token_data = token_res.json()
        access_token = token_data.get('access_token')
        
        if not access_token:
            error = token_data.get('error_description', 'Unknown error')
            logger.error(f"No access token in response: {error}")
            return web.Response(text='Failed to get access token', status=400)
        
        logger.info(f"Got access token: {SecurityUtils.mask_token(access_token)}")
        
        # Get user info from GitHub
        user_res = requests.get(
            'https://api.github.com/user',
            headers={'Authorization': f'token {access_token}'},
            timeout=30
        )
        
        logger.info(f"User response status: {user_res.status_code}")
        
        if user_res.status_code != 200:
            logger.error(f"GitHub user API failed: {user_res.status_code}")
            return web.Response(text='Failed to get user information', status=400)
        
        user_data = user_res.json()
        login = user_data.get('login')
        
        if not login or not InputValidator.validate_github_username(login):
            logger.error(f"Invalid GitHub login: {login}")
            return web.Response(text='Failed to get valid GitHub username', status=400)
        
        logger.info(f"Got GitHub login: {login}")
        
        # Insert user into database
        cur.execute(
            'INSERT OR REPLACE INTO users(discord_id, github_login, validated_at) VALUES(?,?, datetime("now"))', 
            (discord_id, login)
        )
        conn.commit()
        
        logger.info(f"Successfully linked user: discord_id={SecurityUtils.hash_sensitive_data(discord_id)}, github_login={login}")
        
        # Clean up used state
        cur.execute('DELETE FROM oauth_states WHERE state=?', (state,))
        conn.commit()
        
        return web.Response(
            text='GitHub account linked successfully! You can return to Discord and use /log command.',
            status=200
        )
        
    except requests.Timeout:
        logger.error("Timeout during GitHub API calls")
        return web.Response(text='GitHub API timeout', status=504)
    except requests.RequestException as e:
        logger.error(f"GitHub API error: {e}")
        return web.Response(text='GitHub API error', status=502)
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        return web.Response(text='Internal server error', status=500)

# Health check endpoint
@routes.get('/health')
async def health_check(request):
    """Health check endpoint."""
    try:
        # Test database connection
        cur.execute('SELECT 1')
        return web.json_response({'status': 'healthy', 'database': 'connected'})
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return web.json_response({'status': 'unhealthy', 'error': str(e)}, status=500)

# Root endpoint for basic connectivity test
@routes.get('/')
async def root(request):
    """Root endpoint for basic connectivity test."""
    return web.Response(text='OAuth Server is running!', status=200)

app = web.Application()
app.add_routes(routes)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting OAuth server on port {port}")
    logger.info(f"OAuth server app routes: {[str(route) for route in app.router.routes()]}")
    web.run_app(app, port=port, host='0.0.0.0')