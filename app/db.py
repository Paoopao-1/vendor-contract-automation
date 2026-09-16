from supabase import create_client, Client
from app.config import SUPABASE_URL, SUPABASE_KEY

_client = None

def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client