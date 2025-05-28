import os

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import credentials, firestore

# .env 파일에서 환경변수 자동 로드
load_dotenv()

FIREBASE_KEY_PATH = os.getenv("FIREBASE_KEY_PATH")

firebase_app = None


def init_firebase():
    global firebase_app
    if not firebase_admin._apps:
        if not FIREBASE_KEY_PATH:
            raise RuntimeError("FIREBASE_KEY_PATH 환경변수가 설정되어 있지 않습니다.")
        cred = credentials.Certificate(FIREBASE_KEY_PATH)
        firebase_app = firebase_admin.initialize_app(cred)
    else:
        firebase_app = firebase_admin.get_app()
    return firestore.client()


# FastAPI에서 사용할 Firestore 클라이언트 반환
_db = None


def get_db():
    global _db
    if _db is None:
        _db = init_firebase()
    return _db
