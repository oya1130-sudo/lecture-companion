# 개인용 클라우드 VM 배포

이 구성은 한 사람이 자기 ChatGPT 계정으로 사용하는 개인용 배포를 전제로 합니다. Streamlit과 Codex CLI는 하나의 Docker 컨테이너에서 실행하고, 업로드·캐시·완성본·Codex 로그인 정보는 Docker 영구 볼륨에 보관합니다. 웹 포트는 호스트의 `127.0.0.1`에만 열고 Tailscale Serve로 본인의 기기에만 HTTPS 접속을 허용합니다.

비용 없이 시작하는 Oracle Cloud ARM VM의 화면별 설정과 무료 한도는 [Oracle Cloud 무료 배포 안내](ORACLE_FREE_DEPLOYMENT.md)를 참고하세요. 이 문서는 공급자와 무관한 유료 VM의 공통 절차입니다.

## 1. VM 준비

권장 시작 사양은 다음과 같습니다.

- Ubuntu 24.04 LTS
- 4 vCPU, 메모리 8GB
- 영구 디스크 30~50GB
- 한국과 가까운 리전
- 인바운드 방화벽은 SSH만 허용하고 `8501` 포트는 열지 않음

스캔 PDF를 여러 개 동시에 처리하거나 파일 크기가 매우 크면 메모리를 16GB로 올립니다. AWS, Google Cloud, Azure 등 Docker를 실행할 수 있는 단일 Linux VM이면 같은 구성을 사용할 수 있습니다.

VM에 [Docker Engine과 Docker Compose 플러그인](https://docs.docker.com/engine/install/ubuntu/)을 설치한 다음 아래 명령이 모두 성공하는지 확인합니다.

```bash
docker --version
docker compose version
```

## 2. 앱 설치

```bash
git clone https://github.com/oya1130-sudo/lecture-companion.git
cd lecture-companion
cp .env.cloud.example .env
chmod 600 .env
docker compose up -d --build
docker compose ps
```

컨테이너에는 OpenAI 공식 Linux 설치기로 Codex CLI가 함께 설치됩니다. 앱은 호스트의 `127.0.0.1:8501`에서만 수신하므로 아직 외부 기기에서는 접속할 수 없습니다.

상태 확인:

```bash
docker compose logs --tail=100 app
curl --fail http://127.0.0.1:8501/_stcore/health
```

## 3. Codex에 ChatGPT 계정으로 로그인

헤드리스 서버에서는 장치 코드 로그인을 사용합니다.

```bash
docker compose exec app codex login --device-auth
```

터미널에 표시된 주소를 개인 브라우저에서 열고 일회용 코드를 입력합니다. 장치 코드 로그인이 보이지 않으면 ChatGPT 보안 설정에서 장치 코드 로그인을 먼저 활성화해야 할 수 있습니다.

로그인 확인:

```bash
docker compose exec app codex login status
```

로그인 정보는 `lecture-companion-data` 볼륨의 `/data/codex`에 저장됩니다. 이 볼륨이나 그 스냅샷에는 접근 토큰이 포함될 수 있으므로 비밀번호처럼 보호합니다.

## 4. Tailscale로 태블릿 접속

VM 호스트와 태블릿에 [Tailscale](https://tailscale.com/download)을 설치하고 같은 계정 또는 같은 tailnet에 연결합니다. VM에서 다음을 실행합니다.

```bash
sudo tailscale up
sudo tailscale serve --bg 8501
tailscale serve status
```

`tailscale serve status`에 표시된 `https://...ts.net` 주소가 앱 주소입니다. 태블릿에서 Tailscale을 켠 뒤 이 주소를 엽니다. Tailscale Funnel은 공개 인터넷 노출 기능이므로 이 앱에는 사용하지 않습니다.

사이드바에도 주소를 표시하려면 `.env`의 값을 수정합니다.

```dotenv
PRESTUDY_PUBLIC_URL=https://서버이름.tailnet이름.ts.net
```

설정을 반영합니다.

```bash
docker compose up -d
```

## 5. 첫 사용

클라우드 VM에는 Google Drive 데스크톱 폴더가 없으므로 첫 버전에서는 `기기에서 업로드`를 사용합니다.

1. `기본 학습가이드 확인·교체`에서 학습가이드 PDF를 등록합니다.
2. 과목을 선택합니다. 교수명과 수업 제목은 족첵 파일명에서 자동으로 읽습니다.
3. 족첵과 선택적인 써머리를 업로드합니다. 족첵에 강의록이 없다면 `강의자료 (선택)`에도 강의자료 PDF를 업로드합니다.
4. 작업 완료 후 HTML을 다운로드합니다.

학습가이드, 업로드, 분석 캐시, 완성 HTML과 작업 이력은 영구 볼륨에 남습니다. 서버가 재시작되면 완료된 작업 이력은 복구됩니다. 재시작 시 실행 중이던 작업은 안전하게 실패 처리되며 다시 제출해야 합니다.

## 6. 업데이트와 운영

업데이트:

```bash
git pull --ff-only
docker compose up -d --build
```

로그 확인:

```bash
docker compose logs -f --tail=100 app
```

재시작:

```bash
docker compose restart app
```

종료:

```bash
docker compose down
```

`docker compose down -v`는 영구 볼륨까지 삭제하므로 사용하지 않습니다.

## 백업과 보안

`lecture-companion-data` 볼륨에는 다음 자료가 함께 있습니다.

- 원본 PDF와 기본 학습가이드
- 분석 캐시와 완성 HTML
- 작업 이력
- Codex 로그인 토큰

VM 공급자의 암호화된 디스크 스냅샷을 사용하고, 스냅샷 접근 권한도 최소화합니다. 저장소, 일반 메신저, 공개 버그 리포트에 볼륨 내용이나 인증 파일을 올리지 않습니다.

이 배포는 단일 사용자·단일 컨테이너 전용입니다. 컨테이너 복제 수를 늘리면 메모리 작업 큐와 로컬 파일의 일관성이 깨질 수 있습니다. 여러 사용자를 지원하려면 사용자 인증, 외부 작업 큐, 데이터베이스와 오브젝트 스토리지를 별도로 설계해야 합니다.
