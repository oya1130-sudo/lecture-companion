# 아키텍처

## 실행 흐름

```text
Streamlit UI
  ├─ 개인 학습가이드 설정
  ├─ Google Drive 마운트 또는 파일 업로드
  └─ JobManager 작업 큐
       └─ StudyGuideService
            ├─ DigestCache: PDF별 분석 재사용
            ├─ CodexStudyEngine: ChatGPT 로그인 Codex CLI
            ├─ GuideCache: 최종 구조화 노트 재사용
            └─ HTML renderer
                 ├─ 로컬 output
                 └─ Google Drive 과목별 폴더
```

## 모듈

- `web.py`: 입력, 최초 설정, 작업 상태, 다운로드 UI
- `jobs.py`: 강의 단위 백그라운드 큐와 Drive 복사
- `service.py`: 캐시, PDF 분석, 합성, 렌더링 조율
- `ai.py`: 격리 작업 폴더에서 `codex exec` 실행
- `prompts.py`: 자료 유형별 분석 및 합성 지침
- `models.py`: Pydantic 구조화 결과 모델
- `html_renderer.py`: 태블릿용 단일 HTML 생성
- `storage.py`: 개인 저장 위치와 Drive 자동 탐색

## 병렬성과 캐시

- 강의 작업 기본 동시 수: 3
- 한 강의의 미분석 자료 기본 동시 수: 2
- 전체 Codex 프로세스 기본 동시 수: 2

환경변수 `PRESTUDY_JOB_WORKERS`, `PRESTUDY_SOURCE_WORKERS`, `PRESTUDY_CODEX_CONCURRENCY`로 조절합니다. 같은 자료·강의 조건·모델은 캐시를 사용합니다.

## 신뢰 경계

PDF 내부 문장은 사용자 지시가 아니라 분석 대상입니다. 업로드 이름은 basename으로 제한하고, Drive 선택 경로는 설정된 자료 루트 내부인지 재검증합니다. Codex 실행에는 API 키 관련 환경변수를 전달하지 않습니다.
