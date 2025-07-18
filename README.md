# Discord Volunteer Tracker Bot

A Discord bot that tracks volunteer hours by validating GitHub commits through OAuth2 integration. Perfect for open source projects, hackathons, and volunteer organizations.

## Features

- **Secure OAuth2 Integration**: Link Discord and GitHub accounts securely
- **Commit Validation**: Automatically detect and validate recent GitHub pushes
- **Hour Logging**: Track volunteer hours per commit with easy selection
- **History & Reports**: View your contribution history and statistics
- **Security**: Rate limiting, input validation, and secure token handling
- **User-Friendly**: Intuitive Discord slash commands

## Quick Start

### Prerequisites

- Python 3.9 or higher
- Discord Bot Token
- GitHub OAuth App credentials
- Basic knowledge of Discord bot setup

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/discord-volunteer-tracker
cd discord-volunteer-tracker
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up Environment Variables

Create a `.env` file in the project root:

```env
# Discord Bot Configuration
DISCORD_TOKEN=your_discord_bot_token_here
LOG_CHANNEL_ID=optional_log_channel_id

# GitHub OAuth Configuration
GITHUB_CLIENT_ID=your_github_oauth_client_id
GITHUB_CLIENT_SECRET=your_github_oauth_client_secret
GITHUB_TOKEN=your_github_personal_access_token

# OAuth Server Configuration
OAUTH_REDIRECT_URI=http://localhost:8000
```

### 4. Set Up GitHub OAuth App

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click "New OAuth App"
3. Fill in the details:
   - **Application name**: Discord Volunteer Tracker
   - **Homepage URL**: `http://localhost:8000`
   - **Authorization callback URL**: `http://localhost:8000/oauth/callback`
4. Copy the Client ID and Client Secret to your `.env` file

### 5. Run the Bot

Start the OAuth server:
```bash
python oauth_server.py
```

In another terminal, start the Discord bot:
```bash
python bot.py
```

## Commands

| Command | Description | Usage | Example |
|---------|-------------|-------|---------|
| `/link` | Get OAuth link to connect GitHub | `/link` | `/link` |
| `/log` | Log volunteer hours for a commit | `/log hours:2` | `/log hours:3.5` |
| `/history` | View recent volunteer logs | `/history limit:5` | `/history limit:10` |
| `/status` | Check GitHub account status | `/status` | `/status` |

### Command Details

#### `/link`
Generates a secure OAuth link to connect your Discord account with GitHub. Click the link and authorize the application.

#### `/log hours:<number>`
Log volunteer hours for a recent GitHub commit:
- Hours must be between 0 and 24
- Shows commits from the last 7 days
- Select from a dropdown menu of your commits
- 10-second cooldown between uses

#### `/history limit:<number>`
View your recent volunteer hour logs:
- Limit between 1 and 20 entries
- Shows commit ID, hours, and timestamp
- Displays total hours logged

#### `/status`
Check your GitHub account connection status:
- Shows linked GitHub username
- Displays when account was linked
- Shows recent commit count

## Architecture

- **Discord Bot** (`bot.py`): Handles slash commands and user interactions
- **OAuth Server** (`oauth_server.py`): Manages GitHub authentication flow
- **Database** (`db.py`): SQLite database with user, commit, and log tables
- **GitHub Utils** (`github_utils.py`): GitHub API integration for commit validation

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_TOKEN` | Yes | Discord bot token from Discord Developer Portal |
| `GITHUB_CLIENT_ID` | Yes | GitHub OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | Yes | GitHub OAuth app client secret |
| `GITHUB_TOKEN` | Yes | GitHub personal access token for API calls |
| `OAUTH_REDIRECT_URI` | Yes | Base URL for OAuth server (e.g., `http://localhost:8000`) |
| `LOG_CHANNEL_ID` | No | Discord channel ID for bot logs |

### Database Schema

- **users**: Discord ID, GitHub login, validation timestamp
- **commits**: Commit SHA, GitHub login, commit date
- **logs**: Volunteer hour logs with commit reference
- **oauth_states**: Temporary OAuth state tokens

## Development

### Project Structure

```
discord-volunteer-tracker/
├── bot.py              # Discord bot implementation
├── oauth_server.py     # OAuth2 server for GitHub
├── db.py              # Database operations
├── github_utils.py    # GitHub API utilities
├── requirements.txt   # Python dependencies
├── .env              # Environment variables
└── README.md         # This file
```

### Common Issues

#### "You must link your GitHub first"
- Ensure you completed the OAuth flow
- Check that your Discord ID matches in the database
- Try the `/status` command to verify your connection

#### "No GitHub commits found"
- Make sure you have recent commits in the last 7 days
- Verify your GitHub token has the correct permissions
- Check that commits are in public repositories

#### OAuth Server Errors
- Ensure all environment variables are set correctly
- Check that the OAuth callback URL matches your GitHub app settings
- Verify the server is running on the correct port (localhost:8000)

#### Database Issues
- Delete `volunteer.db` to reset the database
- Check file permissions for the database file
- Ensure both bot and OAuth server use the same database file

#### Port Issues
- Try Railway.com as host or download version 1.0 of OAuth_Server.py file, Railway's PORT variable is used in newer version of the project. 

### Debug Mode

Enable debug logging by setting the log level:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
