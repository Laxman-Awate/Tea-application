# Vercel serverless entry point
from app import app

# Vercel requires this handler
handler = app

# Export for Vercel
__all__ = ['handler']
