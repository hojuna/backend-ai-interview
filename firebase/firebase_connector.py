import firebase_admin
from firebase_admin import credentials, firestore

# config.py에서 settings 객체 임포트
from .config import settings # 현재 디렉토리의 config.py에서 settings 임포트


db = None # Firestore 클라이언트 인스턴스를 저장할 전역 변수
_firebase_app_instance = None # Firebase 앱 인스턴스 저장용

try:
    if not firebase_admin._apps:
        # settings 객체를 통해 키 파일 경로를 가져옴
        service_account_key_path = settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH
        
        if not service_account_key_path: # 경로가 비어있는지 한번 더 확인
            raise ValueError("FIREBASE_SERVICE_ACCOUNT_KEY_PATH 설정값이 비어있습니다.")

        cred = credentials.Certificate(service_account_key_path)
        _firebase_app_instance = firebase_admin.initialize_app(cred) # 앱 인스턴스 저장
        print(f"Firebase Admin SDK 초기화 완료 (Connector) - 프로젝트 ID: {_firebase_app_instance.project_id}")
    else:
        # 이미 앱이 초기화된 경우, 해당 앱 인스턴스를 가져와 _firebase_app_instance에 할당
        _firebase_app_instance = firebase_admin.get_app() # 기본 앱 인스턴스 가져오기
        print(f"Firebase Admin SDK가 이미 초기화되었습니다 (Connector) - 프로젝트 ID: {_firebase_app_instance.project_id}")


    # Firestore 클라이언트 가져오기
    # 이제 _firebase_app_instance는 항상 유효한 앱 인스턴스를 참조 (성공 시)
    db = firestore.client(app=_firebase_app_instance) # 특정 앱 인스턴스 사용
    print("Firestore client 가져오기 성공 (Connector).")

except FileNotFoundError:
    print(f"Firebase 서비스 계정 키 파일을 찾을 수 없습니다. 경로: {settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH}")
    print("Tip: .env 파일에 FIREBASE_SERVICE_ACCOUNT_KEY_PATH가 정확한 경로로 설정되어 있는지 확인하세요.")
    db = None
except ValueError as ve:
    print(f"Firebase Admin SDK 설정 값 오류 (Connector): {ve}")
    db = None
except Exception as e:
    print(f"Firebase Admin SDK 초기화 중 예외 발생 (Connector): {e}")
    db = None

def get_firestore_client():
    """
    초기화된 Firestore 클라이언트 인스턴스를 반환합니다.
    초기화 실패 시 ConnectionError를 발생시킵니다.
    """
    if db is None:
        raise ConnectionError("Firestore client가 firebase_connector.py에서 초기화되지 못했습니다. 서버 로그 및 .env 설정을 확인하세요.")
    return db

def get_firebase_app():
    """
    초기화된 Firebase 앱 인스턴스를 반환합니다.
    """
    global _firebase_app_instance # 전역 변수 사용 명시
    # _firebase_app_instance가 모듈 로딩 시점에 잘 설정되었다면, 이 부분은 없어도 될 수 있습니다.
    # 하지만 방어적으로 한 번 더 확인하는 로직입니다.
    if not _firebase_app_instance and firebase_admin._apps:
         _firebase_app_instance = firebase_admin.get_app()

    if _firebase_app_instance is None: # 여전히 None이면 초기화 실패
        raise ConnectionError("Firebase 앱이 초기화되지 않았습니다.")
    return _firebase_app_instance