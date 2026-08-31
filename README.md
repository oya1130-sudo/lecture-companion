# 수업 동반 노트 생성기

학습가이드, 족첵, 선택적인 강의자료와 선배 써머리 PDF를 분석해 수업 중 강의록 옆에 띄워 볼 수 있는 단일 HTML 노트를 만듭니다. 강의자료 페이지 순서에 맞춘 필기 대체 노트, 강조점, 들을 포인트, 최소 현장 메모를 제공합니다.

OpenAI API 키를 사용하지 않습니다. 각 사용자가 자기 ChatGPT 계정으로 로그인한 Codex CLI의 구독 사용량을 사용합니다. Codex는 ChatGPT 로그인과 API 키 로그인을 모두 지원하지만, 이 프로그램은 API 키 로그인을 거부합니다. 공식 안내는 [Codex CLI](https://developers.openai.com/codex/cli)와 [OpenAI 인증](https://developers.openai.com/codex/auth)을 참고하세요.

## 주요 기능

- 여러 강의 작업을 큐에 넣고 제한적으로 병렬 처리
- 기본 `빠른 생성` 모드와 PDF 3개 동시 분석, 단계별 소요시간 표시
- PDF별 분석 결과와 완성 노트 캐시
- 태블릿에서 같은 Wi-Fi 주소로 접속
- 메인 노트북에 마운트된 Google Drive 족첵·강의자료·써머리를 직접 검색·선택
- 족첵에 강의록이 없을 때 별도 강의자료를 페이지 기준으로 사용
- 페이지 순서형 로드맵과 파트별 필기 대체 노트
- 기출 중요도(⭐)·기출 연도, 비교표, Cause & Effect 흐름, 🔥 함정 블록과 최종 체크리스트
- 완성 HTML을 로컬과 Google Drive 과목별 폴더에 자동 저장
- PDF 자료와 브라우저 메모를 외부 서버에 따로 저장하지 않는 로컬 실행 구조
- 개인용 클라우드 VM에서 노트북을 꺼도 계속 실행하는 Docker 배포

## Windows 빠른 시작

필요한 항목:

- Windows 10 또는 11
- Python 3.11 이상
- Codex CLI 또는 OpenAI Codex VS Code 확장
- Codex를 사용할 수 있는 ChatGPT 계정

배포 ZIP을 원하는 폴더에 압축 해제하고 `start-app.cmd`를 더블클릭합니다. 최초 실행에는 전용 가상환경과 Python 패키지를 설치하므로 몇 분 걸릴 수 있습니다. Codex 로그인이 없다면 브라우저 로그인 흐름이 시작됩니다.

처음 열린 화면에서 `기본 학습가이드 확인·교체`를 펼쳐 자신의 학습가이드 PDF를 넣고 `선택한 파일을 기본 학습가이드로 저장`을 누릅니다. 이 PDF와 경로 설정은 개인 데이터 영역인 `data`에 저장되며 Git과 공유 ZIP에서 제외됩니다.

기본값인 `빠른 생성`은 Codex 추론 강도를 낮춰 10분 이내 생성을 목표로 합니다. 더 깊은 검토가 필요한 강의만 사이드바의 `고급 설정`에서 `균형`이나 `정밀 생성`을 선택하세요. 실제 시간은 PDF 분량과 Codex 서비스 혼잡도에 따라 달라지며, 작업 큐의 진행 기록에서 PDF별 분석·최종 합성·전체 시간을 확인할 수 있습니다.

자세한 초보자 안내는 [QUICKSTART.md](QUICKSTART.md)를 참고하세요.

## Google Drive

Google Drive 데스크톱 앱이 연결되어 있고 다음 폴더명이 존재하면 자동 탐색합니다.

- `2026 본과 1-2 족첵`
- `의학과 1-2/2026년/학습부`
- `써머리부`
- `내 드라이브`

앱에서 과목을 선택하면 해당 과목 폴더의 PDF만 검색합니다. `강의자료 (선택)`를 고르면 노트의 강의 흐름과 모든 페이지 표시는 강의자료를 기준으로 만들며, 교수명과 수업 제목은 항상 족첵 파일명에서 가져옵니다. 선택하지 않으면 기존처럼 족첵이 페이지 기준입니다.

자동 탐색이 되지 않으면 `PRESTUDY_JOKCHEK_ROOT`, `PRESTUDY_LECTURE_ROOT`, `PRESTUDY_SUMMARY_ROOT`, `PRESTUDY_DRIVE_OUTPUT` 환경변수에 전체 경로를 지정할 수 있습니다. Drive가 없어도 `기기에서 업로드`와 로컬 HTML 다운로드는 사용할 수 있습니다.

## 개인용 클라우드 VM

Docker를 실행할 수 있는 Linux VM에 앱과 Codex CLI를 함께 올리고, Tailscale을 통해 태블릿과 다른 기기에서 안전하게 접속할 수 있습니다. 클라우드 배포에서는 업로드, 캐시, 완성 HTML, 작업 이력과 Codex 로그인을 영구 볼륨에 저장합니다.

비용 없이 먼저 시험하려면 [Oracle Cloud Always Free 배포 안내](docs/ORACLE_FREE_DEPLOYMENT.md)를 따르세요. 서울 리전 ARM VM 1대(2 OCPU·12GB)에 맞춘 설정과 태블릿 접속 절차가 들어 있습니다. 무료 VM은 유휴 상태로 판단되면 회수될 수 있으므로 결과물 백업이 필요합니다.

```bash
git clone https://github.com/oya1130-sudo/lecture-companion.git
cd lecture-companion
cp .env.cloud.example .env
docker compose up -d --build
docker compose exec app codex login --device-auth
```

다른 유료 VM을 쓸 때의 공통 절차는 [개인용 클라우드 VM 배포 안내](docs/CLOUD_DEPLOYMENT.md)를 따르세요. 이 앱은 별도 사용자 인증이 없으므로 `8501` 포트를 공용 인터넷에 직접 열지 않습니다.

## 저장 구조

- `output`: 로컬 완성 HTML
- `data`: 개인 학습가이드와 개인 설정
- `.prestudy-cache`: 재사용 가능한 분석 캐시
- `.prestudy-work`: 격리된 Codex 작업 폴더
- `jobs.json`: 서버 재시작 후 복구되는 완료·실패 작업 이력
- Google Drive `수업 동반 노트/01. 병리학` 등: 동기화되는 완성본

HTML 표지 제목은 `MMDD 과목명 교수명 강의주제` 형식이며, 완성 파일명은 같은 제목 뒤에 `수업동반노트.html`을 붙입니다. 같은 이름이 있으면 `(2)`처럼 번호를 붙입니다.

## 개발

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
```

Windows 배포 ZIP 생성:

```powershell
.\build-share-package.ps1
```

구조와 데이터 흐름은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), GitHub 게시 절차는 [docs/GITHUB.md](docs/GITHUB.md)를 참고하세요.

## 공유 전 주의

PDF 원본, 완성 노트, Google OAuth 파일, Codex 로그인 캐시는 공유하면 안 됩니다. `.gitignore`와 배포 스크립트가 이를 제외하지만 게시 전 `git status`와 ZIP 내용을 다시 확인하세요. 이 앱은 인증 없는 로컬 네트워크 서버이므로 공용 인터넷에 직접 노출하지 마세요. 자세한 내용은 [SECURITY.md](SECURITY.md)에 있습니다.

## 라이선스

아직 오픈소스 라이선스를 선택하지 않았습니다. 비공개 GitHub 저장소나 지인 대상 ZIP 공유는 가능하지만, 공개 저장소에서 재사용·수정 권한을 명확히 하려면 MIT, Apache-2.0 등 원하는 라이선스를 선택해 `LICENSE`를 추가하세요.
