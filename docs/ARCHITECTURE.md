# 아키텍처

## 실행 흐름

```text
Streamlit UI
  ├─ 개인 학습가이드 설정
  ├─ Google Drive 마운트 또는 파일 업로드
  │    └─ 족첵 + 선택적 강의자료 + 선택적 써머리
  └─ JobManager 작업 큐
       ├─ jobs.json: 완료·실패 작업 이력 영속화
       └─ StudyGuideService
            ├─ DigestCache: PDF별 분석 재사용
            ├─ CodexStudyEngine: ChatGPT 로그인 Codex CLI
            ├─ GuideCache: 최종 구조화 노트 재사용
            └─ HTML renderer
                 ├─ 로컬 output
                 └─ Google Drive 과목별 폴더
```

## 실행 형태

### 로컬 Windows

- Streamlit은 로컬 네트워크에서 수신합니다.
- Google Drive 데스크톱의 마운트 폴더를 직접 검색합니다.
- 프로그램을 종료하면 실행 중인 작업도 종료됩니다.

### 개인용 클라우드 VM

```text
태블릿 브라우저
  └─ Tailscale Serve HTTPS
       └─ VM localhost:8501
            └─ Docker: Streamlit + Codex CLI
                 └─ lecture-companion-data 영구 볼륨
                      ├─ Codex 로그인
                      ├─ 업로드와 학습가이드
                      ├─ 분석 캐시와 완성 HTML
                      └─ jobs.json
```

클라우드 컨테이너는 하나만 실행합니다. 현재 작업 큐는 프로세스 메모리에 있으므로 실행 중 재시작된 작업은 재개하지 않고 실패 처리합니다. 완료·실패 작업과 결과 파일은 영구 볼륨에서 복구합니다.

## 모듈

- `web.py`: 입력, 최초 설정, 작업 상태, 다운로드 UI
- `jobs.py`: 강의 단위 백그라운드 큐와 Drive 복사
- `service.py`: 캐시, PDF 분석, 합성, 렌더링 조율
- `ai.py`: 격리 작업 폴더에서 `codex exec` 실행
- `prompts.py`: 자료 유형별 분석 및 합성 지침
- `models.py`: Pydantic 구조화 결과 모델
- `html_renderer.py`: 태블릿용 단일 HTML 생성
- `storage.py`: 개인 저장 위치와 Drive 자동 탐색
- `compose.yaml`: 단일 VM용 컨테이너, 영구 볼륨, localhost 포트 구성
- `Dockerfile`: Streamlit 런타임, 한글 글꼴, Codex CLI 설치

## 병렬성과 캐시

- 강의 작업 기본 동시 수: 3
- 한 강의의 미분석 자료 기본 동시 수: 2
- 전체 Codex 프로세스 기본 동시 수: 2

환경변수 `PRESTUDY_JOB_WORKERS`, `PRESTUDY_SOURCE_WORKERS`, `PRESTUDY_CODEX_CONCURRENCY`로 조절합니다. 같은 자료·강의 조건·모델은 캐시를 사용합니다.

별도 강의자료가 선택되면 합성 단계와 HTML 렌더링 단계 모두 강의자료 인용만 페이지 기준으로 사용합니다. 교수명·수업 제목과 시험 출제 신호는 족첵이 기준이며, 강의자료가 없을 때는 족첵이 내용과 페이지 기준을 함께 담당합니다.

## 신뢰 경계

PDF 내부 문장은 사용자 지시가 아니라 분석 대상입니다. 업로드 이름은 basename으로 제한하고, Drive 선택 경로는 설정된 자료 루트 내부인지 재검증합니다. Codex 실행에는 API 키 관련 환경변수를 전달하지 않습니다.

클라우드에서는 Streamlit 포트를 호스트의 loopback에만 바인딩하고 Tailscale Serve가 HTTPS를 종료합니다. `CODEX_HOME`은 영구 볼륨에 있지만 이미지와 Git 저장소에는 포함되지 않습니다.
