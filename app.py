import os

from e16_app import create_app
from e16_app import models  # noqa: F401

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Security fix: Only enable debug if explicitly set in environment
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() in ["true", "1", "t"]
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
