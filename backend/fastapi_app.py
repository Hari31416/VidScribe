from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import register_routes


app = FastAPI(title="VidScribe API", version="0.1.0")

# Allow access from typical local dev origins. Adjust as needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev; narrow this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_routes(app)
