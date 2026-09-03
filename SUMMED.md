# summed

수업 요약본과 전사본을 직접 업로드해, ChatGPT 구독으로 로그인된 Codex CLI를 이용해 시험용 정리본을 만드는 로컬 앱입니다. 결과는 이미지 없는 Markdown과 단일 HTML 파일로 생성되며 `oya1130@gmail.com`의 Google Drive `summed` 폴더에 저장됩니다.

## 실행

PowerShell에서 다음 명령을 실행합니다.

```powershell
.\run-summed.ps1
```

또는 `start-summed.cmd`나 바탕화면의 `summed` 바로가기를 엽니다. summed는 prestudy와 겹치지 않는 <http://localhost:8502>에서 실행됩니다.

처음 실행하면 필요한 패키지를 설치하고 Codex 로그인을 확인한 뒤 브라우저에서 앱을 엽니다.

## 사용 순서

1. `기본 참고자료` 탭에 족보, 학습가이드, 시간표를 올리고 과목을 지정합니다.
2. `새 정리본` 탭의 `Drive에서 선택`에서 과목과 요약본을 고릅니다. 파일명의 주차·차시·주제를 바탕으로 전사본이 자동 선택되며, 필요하면 선택을 조정합니다. `직접 업로드` 방식도 사용할 수 있습니다.
3. `결과` 탭에서 진행 상황을 보고 MD·HTML을 받거나 미리 봅니다.
4. `설정` 탭에서 Google OAuth 데스크톱 클라이언트 JSON을 등록하고 두 계정을 각각 한 번 승인하면 KHU 내 드라이브에 `summed` 바로가기를 만들 수 있습니다.

PDF에서는 텍스트 레이어만 읽습니다. 이미지나 스캔으로만 된 페이지는 분석하지 않으며, 출력에도 이미지를 넣지 않습니다. 과목별 참고자료 프로필은 파일 구성이 바뀔 때만 다시 만들어 Codex 사용량을 줄입니다.

Drive에서 선택할 때 강의일은 선택된 전사본 중 가장 늦게 업로드된 파일의 날짜가 기본값입니다. 출력 파일명은 원본 요약본 제목의 마지막 `요약본`을 `summed`로 바꿔 `.md`와 `.html`로 저장합니다.

Google Drive가 막 실행된 직후 자료가 보이지 않으면 `Google Drive 다시 검색`을 누릅니다. 앱은 모든 드라이브 문자를 다시 확인하며 Gmail 결과 폴더는 볼륨의 계정명으로 구분합니다.

## 선택 환경변수

- `SUMMED_HOME`: 로컬 데이터와 인증 토큰 저장 위치
- `SUMMED_DRIVE_OUTPUT`: Google Drive for desktop의 Gmail 결과 폴더 경로
- `SUMMED_CODEX_MODEL`: 비워 두면 Codex 로그인 계정의 기본 모델을 사용
- `SUMMED_CONCURRENCY`: 동시에 실행할 작업 수. 기본값 `3`, 허용 범위 `1~4`
- `SUMMED_CODEX_CONCURRENCY`: 이전 버전 호환용 동시 작업 설정
- `SUMMED_NOTE_REASONING_EFFORT`: 개별 정리본 생성 추론 강도. 기본값 `low`
- `SUMMED_PROFILE_REASONING_EFFORT`: 캐시되는 과목 분석 추론 강도. 기본값 `medium`
- `SUMMED_SUMMARY_ROOT`: 자동 탐색 대신 사용할 `00 학습자료` 폴더 전체 경로
- `SUMMED_TRANSCRIPT_ROOT`: 자동 탐색 대신 사용할 `녹음부` 폴더 전체 경로
