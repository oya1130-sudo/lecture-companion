# 보안 및 개인정보

## 공유하면 안 되는 파일

- 강의 PDF와 학습가이드 PDF
- `output`, `data`, `.prestudy-cache`, `.prestudy-work`, `downloads`
- `credentials.json`, `token.json`, `.env`, `.streamlit/secrets.toml`
- `~/.codex/auth.json` 등 Codex 로그인 캐시

Codex 인증 파일에는 접근 토큰이 포함될 수 있습니다. 프로젝트 폴더로 복사하거나 GitHub, 메신저, ZIP에 포함하지 마세요.

## 네트워크 범위

앱은 태블릿 접속을 위해 로컬 네트워크의 `8501` 포트에서 수신하며 별도 사용자 인증이 없습니다. 신뢰하는 개인 Wi-Fi에서만 실행하고 공용 인터넷에 포트포워딩하지 마세요. 작업을 마치면 커맨드창을 닫아 서버를 종료합니다.

## 인증과 사용량

각 설치 사용자는 자기 ChatGPT 계정으로 Codex에 로그인해야 합니다. 프로그램은 환경의 API 키 변수를 제거하고 `codex login status` 결과가 ChatGPT 로그인이 아니면 실행을 중단합니다.

## 취약점 제보

공개 GitHub 저장소를 만든 뒤에는 일반 Issue에 실제 PDF, 경로, 토큰, 화면 전체 로그를 올리지 말고 저장소 소유자에게 비공개로 전달할 연락 방법을 이 문서에 추가하세요.
