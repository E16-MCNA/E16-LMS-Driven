from e16_app import create_app
from e16_app import models  # noqa: F401

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
