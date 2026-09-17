"""
Supabase client initialization.
Provides both the standard client (for auth/RLS) and a service-role client (for backend ops).
"""

from supabase import create_client, Client
from src.config import settings

# Standard client — respects RLS policies, used for user-facing operations
_supabase_client: Client | None = None

# Service-role client — bypasses RLS, used for backend data ingestion
_supabase_admin: Client | None = None


def get_supabase() -> Client:
    """Get the standard Supabase client (respects RLS)."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(
            settings.supabase_url,
            settings.supabase_anon_key
        )
    return _supabase_client


def get_supabase_admin() -> Client:
    """Get the service-role Supabase client (bypasses RLS for backend ops)."""
    global _supabase_admin
    if _supabase_admin is None:
        _supabase_admin = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key
        )
    return _supabase_admin
