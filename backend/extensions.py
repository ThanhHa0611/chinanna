
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS

_tunnel_env = Path(__file__).resolve().parent / ".env.public-tunnel"
load_dotenv()
if _tunnel_env.is_file():
    load_dotenv(_tunnel_env, override=True)

app = Flask(__name__)


def create_app():
    """Create and configure the Flask application."""
    _cors_extra = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    CORS(
        app,
        origins=[
            r"http://localhost:\d+",
            r"http://127\.0\.0\.1:\d+",
            r"https://.*\.trycloudflare\.com",
            r"https://.*\.vercel\.app",
            *_cors_extra,
        ],
        supports_credentials=True,
    )
    import middleware  # noqa: F401 — registers hooks

    import routes.admin_access  # noqa: F401
    import routes.admin_auth  # noqa: F401
    import routes.admin_documents  # noqa: F401
    import routes.admin_feedback  # noqa: F401
    import routes.admin_inbox  # noqa: F401
    import routes.admin_mentees  # noqa: F401
    import routes.admin_profile_activities  # noqa: F401
    import routes.admin_stats  # noqa: F401
    import routes.auth  # noqa: F401
    import routes.cron  # noqa: F401
    import routes.documents  # noqa: F401
    import routes.email_actions  # noqa: F401
    import routes.feedback  # noqa: F401
    import routes.health  # noqa: F401
    import routes.l1_email_actions  # noqa: F401
    import routes.misc  # noqa: F401
    import routes.parent  # noqa: F401
    import routes.profile_activities  # noqa: F401
    import routes.superadmin  # noqa: F401

    return app
