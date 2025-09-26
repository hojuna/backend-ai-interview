from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.api import sessions
from app.core.firebase import init_firebase

app = FastAPI()

# CORS
origins = [
    "http://localhost:5173",  # Vite 개발 서버 주소
    "http://172.17.0.2:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Firebase 초기화 (앱 시작 시)
init_firebase()

app.include_router(sessions.router)
app.mount("/reports", StaticFiles(directory="reports"), name="reports")
