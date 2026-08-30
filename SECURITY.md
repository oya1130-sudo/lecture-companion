# 보안 및 개인정보

## 공유하면 안 되는 파일

- 강의 PDF와 학습가이드 PDF
- `output`, `data`, `.prestudy-cache`, `.prestudy-work`, `downloads`
- `credentials.json`, `token.json`, `.env`, `.streamlit/secrets.toml`
- `~/.codex/auth.json` 등 Codex 로그인 캐시

Codex 인증 파일에는 접근 토큰이 포함될 수 있습니다. 프로젝트 폴더로 복사하거나 GitHub, 메신저, ZIP에 포함하지 마세요.

## 네트워크 범위

앱은 태블릿 접속을 위해 로컬 네트워크의 `8501` 포트에서 수신하며 별도 사용자 인증이 없습니다. 신뢰하는 개인 Wi-Fi에서만 실행하고 공용 인터넷에 포트포워딩하지 마세요. 작업을 마치면 커맨드창을 닫아 서버를 종료합니다.

클라우드 Docker 구성은 호스트의 `127.0.0.1:8501`에만 포트를 바인딩합니다. Tailscale Serve 같은 인증된 비공개 네트워크를 통해서만 접속하고, 클라우드 방화벽에서 `8501` 포트를 열거나 Tailscale Funnel을 사용하지 마세요.

## 클라우드 영구 볼륨

`lecture-companion-data` 볼륨에는 PDF, 완성본, 분석 캐시뿐 아니라 `/data/codex` 아래의 Codex 로그인 토큰도 들어갈 수 있습니다. 다음 항목을 지킵니다.

- 볼륨과 VM 디스크를 암호화합니다.
- 스냅샷과 백업 접근 권한을 최소화합니다.
- 볼륨 내용을 GitHub나 공개 저장소에 복사하지 않습니다.
- 서버를 양도하거나 폐기할 때 먼저 `codex logout`을 실행하고 공급자의 디스크 삭제 절차를 따릅니다.
- `docker compose down -v`는 데이터와 인증을 모두 삭제하므로 의도한 초기화가 아니면 실행하지 않습니다.

현재 배포 방식은 한 사람의 ChatGPT 계정을 사용하는 단일 사용자 구성입니다. 다른 사람에게 Tailscale 접근 권한을 부여하면 그 사람이 같은 Codex 구독과 저장 자료에 접근할 수 있으므로 공유하지 마세요.

## 인증과 사용량

각 설치 사용자는 자기 ChatGPT 계정으로 Codex에 로그인해야 합니다. 프로그램은 환경의 API 키 변수를 제거하고 `codex login status` 결과가 ChatGPT 로그인이 아니면 실행을 중단합니다.

## 취약점 제보

공개 GitHub 저장소를 만든 뒤에는 일반 Issue에 실제 PDF, 경로, 토큰, 화면 전체 로그를 올리지 말고 저장소 소유자에게 비공개로 전달할 연락 방법을 이 문서에 추가하세요.
