# summed Antigravity 인계

**날짜:** 2026-09-03  
**기기:** DESKTOP-5PDKO8N  
**관련 명세:** 없음

## 현재 상태

`main`의 코드 기준점은 `7953594`이다. summed는 기존 prestudy와 분리된 로컬 Streamlit 앱으로 `app.py`/8502에서 실행되며, Drive 자료 선택·직접 업로드, 참고자료 기반 생성, 과목별 HTML 및 `md/` 하위 Markdown 저장, 소단원별 복습 퀴즈, 동시 작업과 실제 시간 기반 진행 기록까지 구현됐다. 최신 `origin/main`의 prestudy 개선 19개 커밋도 rebase로 보존했다.

## 이번 세션에 한 일

- 단계별 시각을 작업 JSON에 기록하고 전체·대기·실행 시간과 현재 사항을 2초 간격으로 표시했다.
- 요약본/전사본 추출, 참고자료 분석·캐시, Codex 대기·생성, MD·HTML 변환, Drive 저장을 구분했다.
- summed 전체를 최신 원격 위에 재배치하고 Windows 실행기의 서버 재열기·브라우저 실행을 보강했다.
- PowerShell 구문 검사와 전체 테스트를 실행했다: `94 passed in 10.14s`.

## 내린 결정과 근거

- 불확실한 퍼센트·남은 시간은 표시하지 않는다. Codex 실행 시간은 예측하기 어려워 실제 경과 시간만 보여야 정확하다.
- 자동 갱신은 실행 중 작업에만 2초 주기로 적용하고 완료 후 중단한다. 추가 Codex 호출·토큰 소비 없이 UI 부하를 제한한다.
- 출력은 HTML+Markdown만 만들고, HTML은 과목 폴더 바로 아래, Markdown은 과목별 `md/`에 둔다. PDF는 시인성이 낮아 제외했다.
- 이미지는 입력·출력에서 제외하며 표는 자료상 필요할 때만 생성한다. 토큰 사용과 문서 부피를 줄이기 위함이다.
- prestudy와 summed는 데이터·포트·실행 진입점을 분리한다. 기존 프로그램과 작업 이력을 덮어쓰지 않기 위함이다.

## 고려했다가 안 한 것

| 대안 | 왜 안 했나 |
|---|---|
| PDF도 함께 생성 | 사용자가 HTML이 더 보기 좋다고 판단해 제외했다. |
| Drive 완전 자동 감시 | 사용자가 Codex 사용량을 쓰는 수동 업로드/선택 UI 방식으로 결정했다. |
| 이미지 분석·삽입 | 토큰 소모가 커서 명시적으로 제외했다. |
| 가짜 진행률·예상 완료 시각 | 실제 Codex 소요 시간을 반영하지 못해 오해를 만들 수 있다. |

## 변경한 파일

| 파일 | 무엇을 / 왜 |
|---|---|
| `src/summed/` | 생성 파이프라인, Drive 연동, 파일 처리, 렌더링, 작업 큐·진행 시간, Streamlit UI 전체 |
| `app.py`, `run.ps1`, `run-program.ps1`, `run-summed.ps1`, `start-summed.cmd` | summed 전용 8502 진입점과 안정적인 Windows/브라우저 실행 |
| `SUMMED.md`, `README.md`, `QUICKSTART.md` | 사용법과 prestudy/summed 분리 설명 |
| `.streamlit/config.toml`, `.gitignore`, `pyproject.toml` | 포트·테마, 로컬 데이터 제외, 의존성과 CLI 등록 |
| `tests/test_summed_*.py`, `tests/test_app_separation.py`, `tests/test_deployment.py` | 생성·Drive·동시성·진행 시간·분리·실행기 회귀 검증 |

## 미해결 질문 / 블로커

- 앱 기능 블로커는 없다. 다만 새 진행 UI 이후 실제 Codex+Drive 전체 생성은 토큰 절약을 위해 다시 실행하지 않았고 테스트 대역으로 검증했다.
- 이전 버전에서 끝난 작업은 단계별 시각이 없어 메시지만 표시된다. 새 작업부터 정확한 단계 시간이 남는다.
- `devkit-marketplace/`는 별도 중첩 Git 저장소로 미추적 상태이며 건드리지 않았다.
- Git이 `.git/worktrees/lecture-companion-oracle-b1f47956` 정리 시 권한 경고를 내지만 현재 rebase·커밋·브랜치에는 영향이 없었다.

## 다음 단계

1. `run-summed.ps1`로 실제 요약본+전사본 1건을 생성해 단계 시간, 출력 파일명, Drive의 과목/`md` 배치를 확인한다.
2. 실제 생성에서 Drive 경고가 재현되면 `run-program.ps1`의 `SUMMED_SUMMARY_ROOT`·`SUMMED_TRANSCRIPT_ROOT`와 `src/summed/drive_sources.py` 탐색 결과를 비교한다.
3. `devkit-marketplace/`의 보존 위치를 결정하고, Git worktree 권한 경고가 계속되면 해당 메타데이터 잠금 프로세스를 확인한다.

## 재개 시 읽어야 할 파일

1. `SUMMED.md`
2. `docs/handoffs/2026-09-03-01-summed-antigravity.md`
3. `src/summed/web.py`
4. `src/summed/jobs.py`
5. `src/summed/service.py`
6. `src/summed/drive_sources.py`
7. `run-program.ps1`
8. `tests/test_summed_progress.py`
