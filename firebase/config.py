# config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional # 다른 설정값에 필요할 수 있음

class Settings(BaseSettings):
    # .env 파일 또는 환경 변수에서 읽어올 설정값들을 정의합니다.
    # 타입 힌트를 사용하여 pydantic이 자동으로 타입을 검증하고 변환합니다.
    FIREBASE_SERVICE_ACCOUNT_KEY_PATH: str

    # 다른 필요한 설정값들이 있다면 여기에 추가합니다.
    # 예를 들어, API_KEY: Optional[str] = None
    # DEBUG_MODE: bool = False

    model_config = SettingsConfigDict(
        env_file='.env',         # .env 파일의 이름 (기본값)
        env_file_encoding='utf-8', # .env 파일 인코딩
        extra='ignore'           # 모델에 정의되지 않은 .env 변수는 무시
    )

# 설정 객체 인스턴스 생성
# 이 settings 객체를 다른 파일에서 임포트하여 사용합니다.
settings = Settings()

# 사용 예시 (다른 파일에서):
# from .config import settings
# key_path = settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH