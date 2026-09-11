import os
from app import create_app
from app.db import get_connection, release_connection
from app.models import init_db

env = os.environ.get('FLASK_ENV', 'default')
app = create_app(env)

# Initialise database tables on startup
with app.app_context():
    conn = get_connection()
    try:
        init_db(conn)
        print("Database tables initialised successfully.")
    finally:
        release_connection(conn)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
