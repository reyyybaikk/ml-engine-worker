from app.config.db_client import get_db_connection
import json

def get_schema():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get all tables
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        tables = [row['table_name'] for row in cursor.fetchall()]

        schema = {}
        for table in tables:
            # Get columns for each table
            cursor.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}' AND table_schema = 'public'")
            columns = {row['column_name']: row['data_type'] for row in cursor.fetchall()}
            schema[table] = columns

        print(json.dumps(schema, indent=2))

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_schema()
