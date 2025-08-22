# for ASGI servers (uvicorn, hypercorn)
from src.app import create_app
app = create_app()