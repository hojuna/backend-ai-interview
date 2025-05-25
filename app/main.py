from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import sessions
from app.core.firebase import init_firebase

app = FastAPI()

# Firebase 초기화 (앱 시작 시)
init_firebase()

app.include_router(sessions.router)
app.mount("/reports", StaticFiles(directory="reports"), name="reports")
