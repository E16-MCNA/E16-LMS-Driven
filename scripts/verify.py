import os
import sys

# Ensure the parent directory is in sys.path so e16_app can be imported regardless of execution method
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from e16_app import create_app

def verify():
    print("Verifying E16 LMS Application Load...")
    try:
        app = create_app()
        with app.app_context():
            # Check if blueprints are registered
            print(f"Blueprints registered: {list(app.blueprints.keys())}")
            if len(app.blueprints) < 5:
                print("Error: Not all blueprints were registered.")
                sys.exit(1)
        print("Application loaded successfully!")
    except Exception as e:
        print(f"Failed to load application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    verify()
