import sys
import os
from pathlib import Path

# Add campus-companion-py directory to python path
current_dir = Path(__file__).resolve().parent
project_dir = current_dir.parent / "campus-companion-py"
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

from app import app as flask_app


class VercelPathFixer:
    """
    WSGI middleware that restores original requested client URL
    when Vercel rewrites internal paths to /api/index.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        forwarded_uri = (
            environ.get("HTTP_X_FORWARDED_URI")
            or environ.get("HTTP_X_MATCHED_PATH")
            or environ.get("HTTP_X_NOW_ROUTE_MATCHES")
        )
        if forwarded_uri:
            path_only = forwarded_uri.split("?")[0]
            current_path = environ.get("PATH_INFO", "")
            if current_path in ("/api/index", "/api", "/api/index.py", "") or not current_path:
                environ["PATH_INFO"] = path_only
        return self.wsgi_app(environ, start_response)


flask_app.wsgi_app = VercelPathFixer(flask_app.wsgi_app)
app = flask_app
