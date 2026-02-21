"""Supabase client (optional)."""
from typing import Optional

from config import get_settings


_supabase = None


def init_supabase() -> Optional[object]:
    """Initialize Supabase client if URL and key are set."""
    global _supabase
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_key:
        return None
    try:
        from supabase import create_client
        _supabase = create_client(s.supabase_url, s.supabase_service_key)
        return _supabase
    except Exception:
        return None


def get_supabase():
    """Return Supabase client or None."""
    global _supabase
    if _supabase is None:
        init_supabase()
    return _supabase
