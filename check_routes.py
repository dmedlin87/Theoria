"""Diagnostic script to check registered routes in the FastAPI app."""
import os

os.environ["THEO_AUTH_ALLOW_ANONYMOUS"] = "1"
os.environ["THEO_ALLOW_INSECURE_STARTUP"] = "1"
os.environ.setdefault("THEORIA_ENVIRONMENT", "development")

from theo.services.api.app.main import app

print("Registered routes:")
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        methods = getattr(route, 'methods', set())
        print(f"  {methods} {route.path}")
    elif hasattr(route, 'path'):
        print(f"  {route.path}")

print(f"\nTotal routes: {len(app.routes)}")
