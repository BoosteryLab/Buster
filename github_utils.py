import requests
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

def validate_github_user(login: str, token: str) -> bool:
    """
    Validate if a GitHub username exists and is accessible.
    
    Args:
        login: GitHub username to validate
        token: GitHub API token
    
    Returns:
        True if user exists and is accessible, False otherwise
    """
    if not login or not token:
        return False
    
    try:
        url = f'https://api.github.com/users/{login}'
        r = requests.get(url, headers={'Authorization': f'token {token}'})
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Error validating GitHub user {login}: {e}")
        return False

def get_recent_commits(login: str, token: str, since_iso: str) -> List[Dict]:
    """
    Get recent commits for a GitHub user from their public events.
    
    Args:
        login: GitHub username
        token: GitHub API token
        since_iso: ISO timestamp to filter commits from
    
    Returns:
        List of commit dictionaries with id, message, and date
    """
    if not login or not token or not since_iso:
        return []
    
    try:
        url = f'https://api.github.com/users/{login}/events'
        r = requests.get(url, headers={'Authorization': f'token {token}'})
        
        if r.status_code != 200:
            logger.error(f"Failed to get events for {login}: {r.status_code}")
            return []
        
        events = r.json()
        commits = []
        
        for event in events:
            if event['type'] == 'PushEvent':
                for commit in event['payload']['commits']:
                    # Only include commits from the specified time period
                    if event['created_at'] >= since_iso:
                        commits.append({
                            'id': commit['sha'],
                            'message': commit['message'],
                            'date': event['created_at'],
                            'repo': event['repo']['name'] if 'repo' in event else 'unknown'
                        })
        
        # Sort by date (newest first)
        commits.sort(key=lambda x: x['date'], reverse=True)
        
        logger.info(f"Found {len(commits)} commits for {login} since {since_iso}")
        return commits
        
    except Exception as e:
        logger.error(f"Error getting commits for {login}: {e}")
        return []