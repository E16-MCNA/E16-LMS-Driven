# -*- coding: utf-8 -*-
import os
import re

test_dir = r"c:\Users\Admin\OneDrive - Hanoi University of Science and Technology\Desktop\E16\E16\tests"

# Matches @pytest.fixture def app(): and all its contents down to db.drop_all()
app_pattern = re.compile(
    r"@pytest\.fixture\s+def app\(\):.*?(?:yield app\s+db\.drop_all\(\)|yield app\n\s+db\.drop_all\(\))",
    re.DOTALL
)

# Matches @pytest.fixture def client(app): down to return app.test_client()
client_pattern = re.compile(
    r"@pytest\.fixture\s+def client\(app\):\s+return app\.test_client\(\)",
    re.DOTALL
)

def main():
    for filename in os.listdir(test_dir):
        if filename.startswith("test_") and filename.endswith(".py") and filename != "test_storage.py":
            filepath = os.path.join(test_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Replace local app and client fixtures
            new_content = app_pattern.sub("", content)
            new_content = client_pattern.sub("", new_content)
            
            # Remove any trailing extra spaces/newlines that resulted from cleaning
            new_content = re.sub(r"\n{3,}", "\n\n", new_content)
            
            if new_content != content:
                print(f"Successfully cleaned redundant fixtures in {filename}")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)

if __name__ == "__main__":
    main()
