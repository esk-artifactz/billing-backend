import os
import uvicorn
from app import create_app

env = os.environ.get('APP_ENV', 'default')
app = create_app(env)

if __name__ == '__main__':
    uvicorn.run(
        'run:app',
        host='0.0.0.0',
        port=8000,
        reload=True,
    )
