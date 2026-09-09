# SUMMED 렌더러 시각화 개편 및 Drive 동적 연결 Codex 인계

**날짜:** 2026-09-09
**기기:** DESKTOP-5PDKO8N
**관련 명세:** 없음

## 현재 상태

SUMMED 구현 코드 커밋은 `b3e97c7`에 기록돼 있다. 모든 강의 정리본 노트의 시각화 디자인이 고밀도 카드 구조로 표준화되었고, 번호 항목의 기계적 Step 파이프라인 왜곡이 반응형 Category Grid로 전면 개편되었다. Google Drive 마운트의 실시간 동적 탐색이 적용되어 `Gmail Google Drive가 이 PC에 연결되어 있지 않습니다.` 오류가 해결되었으며, 전체 24개 과목 정리본 노트가 재렌더링되어 `G:\내 드라이브\summed\`에 최신 동기화된 상태다. 현재 앱은 로컬 8502 포트에서 정상 가동 중이며 전체 테스트 99건이 모두 통과했다(`99 passed in 23.13s`).

## 이번 세션에 한 일

- **시각화 렌더러 전면 개편 (`src/summed/renderer.py`)**:
  - '병리학 1주차(A)' 수준의 고밀도 카드 뷰 통일: 메타 헤더, 개념 카드(`concept-block`), 다열 매트릭스 그리드(`matrix-grid`), 능동 회상 토글 퀴즈(`quiz-card`), 교수님 강의 강조(`callout.transcript`), 시험 적중/족보 레이더(`callout.exam`).
  - 사용자가 지적한 과도한 배경 형광펜 처리(`mark.kw-mark`, `.kw-mark`)를 제거하여 본문이 태그처럼 어지러워 보이던 현상 해결.
  - `_clean_text` 내부의 따옴표-화살표 충돌 버그(`‘arr-hl’ >➔`) 및 "반면/비교/나뉜다" 기반의 취약한 문장 분할로 인한 가짜 개념 카드(`세포`, `명칭` 등) 완전 제거.
- **번호 항목 지능형 파서 구축 (`_parse_smart_list`)**:
  - 소수점 숫자(`3.2 billion`, `1.5%`, `1.56`)를 단계 번호로 오인하여 `Step 3`, `Step 1: 56이` 등으로 쪼개지던 결함을 정규식 `(?<!\d)[1-9]\.(?!\d)`로 원천 차단.
  - 시계열 순서가 있는 진짜 기전(쇼크 3단계, 염증 5R 등)에만 `step-pipeline`을 적용하고 단계 뱃지 정상화.
  - 병렬적 원인·분류·인자(세포손상 7대 원인, 감염 6군, Virchow triad 등)는 신규 2~3열 반응형 **`category-grid`** 카드로 개편하고 결론 문장은 독립된 하단 콜아웃(`category-note`)으로 분리.
- **Google Drive 동적 마운트 탐색 및 작업 복구 (`src/summed/drive.py`)**:
  - `MountedDrivePublisher.root`를 `@property`로 개편하여 파일 게시(`publish`) 시점마다 현재 PC에 연결된 드라이브(`G:\내 드라이브` 등)를 실시간 동적 탐색하도록 수정.
  - 영문 Windows 경로(`My Drive`) 및 볼륨 라벨 폴백 추가.
  - 실패했던 작업(`약리학 · 자율신경계 약리학 1`, 작업 ID `20260905-125819-da58cb`)을 즉시 복구 및 Google Drive 업로드 완료 (`상태: 완료`).
- **전 과목 24개 강의 노트 일괄 재렌더링 및 구글 드라이브 동기화 완료**:
  - 재렌더링 유틸리티 스크립트(`scripts/re_render_all_notes.py`)를 통해 기존 생성 잡 전체를 최신 양식으로 갱신.

## 내린 결정과 근거

- **Category Grid와 Step Pipeline의 엄격한 분기**:
  - 세포 손상 원인 7가지나 혈전 형성 요인 3가지는 '절차적 단계(Step)'가 아니라 '병렬적 분류'다. 이를 기계적으로 `Step ①`, `Step ②`로 표시하면 의학적으로 왜곡되므로, 2~3열 카드 그리드(`category-grid`)를 새로 도입하고 말미 임상 팁을 분리했다.
- **Drive 마운트 경로의 동적 프로퍼티화**:
  - 서버 부팅 시점에 Google Drive 가상 드라이브가 아직 마운트되지 않았더라도, 사용자가 작업을 실행하거나 완료할 때는 이미 Drive가 켜져 있는 경우가 많다. 생성 완료 시점마다 실시간으로 드라이브를 찾도록 하여 영구적인 `FileNotFoundError` 박제 현상을 방지했다.
- **배경 하이라이트 노이즈 제거**:
  - 글자색과 볼드에 더해 배경에 형광펜까지 치면 텍스트가 태그처럼 지저분해 보인다는 사용자 피드백을 수용하여 형광펜 배경을 걷어내고 타이포그래피 계층으로 강조했다.

## 고려했다가 안 한 것

| 대안 | 왜 안 했나 |
|---|---|
| Step 7의 텍스트 파싱 오류만 땜질 수정 | 7가지 원인을 'Step'으로 표현하는 것 자체가 의학적으로 난센스이며 가로 바가 비어 보이므로, 반응형 그리드로 전면 개편했다. |
| OpenAI API / API 키 결제 방식으로 Drive 동기화 재시도 | SUMMED 아키텍처 불변조건(ChatGPT 구독 기반 로컬 Codex CLI 사용 원칙)에 위배된다. |
| Streamlit 서버 재시작 시 메모리 캐시 유지 | 코드 변경사항(`drive.py`)이 적용되도록 백그라운드 프로세스를 재시작해 즉시 반영했다. |

## 변경한 파일

| 파일 | 무엇을 / 왜 |
|---|---|
| `AGENTS.md` | 자율 실행 모드 및 인계 불변조건 명시 |
| `src/summed/renderer.py` | 지능형 파서 `_parse_smart_list`, `category-grid` 스타일 및 마크업, 의학 용어 뱃지 및 제목 매핑 |
| `src/summed/drive.py` | `MountedDrivePublisher.root` 동적 프로퍼티화, `My Drive` 및 볼륨 라벨 다국어 탐색 강화 |
| `src/prestudy/html_renderer.py` | UI 렌더링 스타일 및 키워드 강조 일관성 개선 |
| `tests/test_summed_renderer.py` | 신규 렌더러 및 파이프라인/그리드 검증 테스트 추가 |
| `scripts/re_render_all_notes.py` | 기존 23개 잡의 `result.json`을 읽어 최신 렌더러로 일괄 재렌더링하고 Drive에 동기화하는 유틸리티 |
| `scripts/migrate_html_ui.py` | HTML 구조 일괄 마이그레이션 스크립트 |

## 미해결 질문 / 블로커

- 앱 기능 블로커는 확인되지 않았다.
- `devkit-marketplace/`는 별도 중첩 Git 저장소로 계속 미추적 상태다.
- `.git/worktrees/lecture-companion-oracle-b1f47956` 정리 시 권한 경고가 계속되지만 커밋과 푸시에는 영향이 없다.

## 다음 단계

1. Codex 세션에서 `docs/handoffs/2026-09-09-01-summed-codex-handoff.md`를 읽고 상태를 파악한다 (또는 `$devkit-resume` 사용).
2. 브라우저에서 `http://localhost:8502`에 접속하여 복구된 `약리학 · 자율신경계 약리학 1` 작업 및 전체 목록이 정상 표시되는지 확인한다.
3. 신규 강의 요약본 1건을 새로 생성하여 분석부터 Google Drive 업로드까지 전체 파이프라인 E2E 정상 작동을 점검한다.

## 재개 시 읽어야 할 파일

1. `AGENTS.md`
2. `SUMMED.md`
3. `docs/handoffs/2026-09-09-01-summed-codex-handoff.md`
4. `src/summed/renderer.py`
5. `src/summed/drive.py`
6. `src/summed/jobs.py`
