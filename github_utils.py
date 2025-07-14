import requests

def validate_github_user(login, token):
    url = f'https://api.github.com/users/{login}'
    r = requests.get(url, headers={'Authorization': f'token {token}'})
    return r.status_code == 200

def get_recent_commits(login, token, since_iso):
    # GET /repos/:owner/:repo/commits CAN require repo; or list user events
    url = f'https://api.github.com/users/{login}/events'
    r = requests.get(url, headers={'Authorization': f'token {token}'})
    events = r.json() if r.status_code == 200 else []
    commits = []
    for e in events:
        if e['type'] == 'PushEvent':
            for c in e['payload']['commits']:
                commits.append({
                    'id': c['sha'],
                    'message': c['message'],
                    'date': e['created_at']
                })
    # filtrowanie według since_iso
    return [c for c in commits if c['date'] >= since_iso]