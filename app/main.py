from fastapi import FastAPI
from app.api import user_api

app = FastAPI()

app.include_router(user_api.router)