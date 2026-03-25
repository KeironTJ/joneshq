"""Quick debug script to test the chat POST flow."""
import os
os.environ['FLASK_ENV'] = 'development'

from app import create_app, db
from app.models import User, Message
import re

app = create_app()
with app.app_context():
    with app.test_client() as client:
        user = User.query.first()
        if not user:
            print('No users in DB')
            exit()
        print(f'User: {user.username} (ID: {user.id})')

        # Login
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)

        resp = client.get('/familychat')
        print(f'GET /familychat => {resp.status_code}')
        
        if resp.status_code == 302:
            loc = resp.headers.get('Location')
            print(f'  Redirected to: {loc}')
            resp = client.get(loc, follow_redirects=True)
            print(f'  After redirect: {resp.status_code}')

        html = resp.data.decode()
        csrf_match = re.search(r'name="csrf_token".*?value="([^"]+)"', html)
        if csrf_match:
            csrf = csrf_match.group(1)
            print('CSRF token: found')
        else:
            print('CSRF token: NOT FOUND')
            csrf = ''

        # Simulate sendMessage() fetch POST
        resp2 = client.post('/familychat',
            data={'csrf_token': csrf, 'content': 'Test message'},
            headers={'X-Requested-With': 'XMLHttpRequest'})
        print(f'POST /familychat => {resp2.status_code}')
        print(f'  Content-Type: {resp2.content_type}')
        body = resp2.data.decode()
        print(f'  Response body: {body[:300]}')
        
        if 'application/json' in resp2.content_type:
            print('  => POST returned JSON (expected)')
        else:
            print('  => POST returned HTML (form validation FAILED!)')
