import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_ANON_KEY')

print(f'URL: {url}')
if not url or not key:
    print('Missing credentials')
    exit(1)

try:
    print('Connecting to Supabase...')
    db = create_client(url, key)
    print('Fetching colleges...')
    res = db.table('colleges').select('*').limit(1).execute()
    print('Success:', res.data)
except Exception as e:
    print('Error:', e)
