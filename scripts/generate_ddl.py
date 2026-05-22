import os
import sys

# Ensure the parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from e16_app import create_app
from e16_app.extensions import db
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

def generate():
    app = create_app()
    app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://localhost/dummy"
    with app.app_context():
        # Generate full DDL schema in PostgreSQL dialect
        ddl_statements = []
        for table in db.metadata.sorted_tables:
            compiled = CreateTable(table).compile(dialect=postgresql.dialect())
            ddl_statements.append(str(compiled).strip() + ";")
        
        output_file = os.path.join(os.path.dirname(__file__), "supabase_schema.sql")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n\n".join(ddl_statements))
        print(f"Successfully generated PostgreSQL DDL at: {output_file}")

if __name__ == "__main__":
    generate()
