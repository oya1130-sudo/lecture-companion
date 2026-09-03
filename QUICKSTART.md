# 처음 사용하는 사람을 위한 안내

> 현재 기본 앱 `summed`의 사용 순서는 [SUMMED.md](SUMMED.md)를 참고하세요. 아래 내용은 기존 `prestudy` 모듈용 안내입니다.

## 1. 준비

1. ZIP을 다운로드해 원하는 폴더에 완전히 압축 해제합니다.
2. [Python Windows 다운로드](https://www.python.org/downloads/windows/)에서 Python 3.11 이상을 설치합니다. 설치 화면에서 PATH 추가 옵션을 켜는 것이 편합니다.
3. [Codex CLI 공식 안내](https://developers.openai.com/codex/cli)에 따라 Codex CLI 또는 OpenAI Codex VS Code 확장을 준비합니다.

## 2. 실행

prestudy는 기존 `C:\Users\oya11\Desktop\prestudy-pdf` 폴더 또는 바탕화면 `prestudy` 바로가기에서 실행합니다. summed는 현재 프로젝트의 `start-app.cmd`, `start-summed.cmd` 또는 바탕화면 `summed` 바로가기로 실행합니다. 처음에는 Python 패키지를 설치합니다. Codex 로그인이 필요하면 브라우저에서 **Sign in with ChatGPT**를 선택합니다. API 키 방식은 이 프로그램에서 사용할 수 없습니다.

## 3. 개인 자료 설정

웹 화면의 `기본 학습가이드 확인·교체`에서 자신의 학습가이드 PDF를 선택하고 기본 파일로 저장합니다. 공유받은 ZIP에는 다른 사람의 PDF가 포함되어 있지 않습니다.

Google Drive 데스크톱 앱과 수업 자료 바로가기가 연결되어 있으면 과목 선택 후 Drive PDF 목록이 자동으로 나타납니다. 족첵에 족보 문제만 있고 강의록이 없다면 `강의자료 (선택)`에서 학습부 PDF를 함께 고릅니다. 이 경우 페이지 표시는 강의자료를 따르지만 교수명과 수업 제목은 족첵에서 자동으로 읽습니다. 목록이 나타나지 않으면 `기기에서 업로드`를 사용합니다.

## 4. 태블릿 접속

프로그램 왼쪽에 표시되는 `http://192.168...:8501` 주소를 같은 Wi-Fi의 태블릿 브라우저에서 엽니다. Windows 방화벽 창에서는 개인 네트워크만 허용합니다. 메인 노트북과 커맨드창은 계속 켜 둡니다.

## 문제 해결

- `Python 3.11 이상이 필요합니다`: Python 설치 후 커맨드창을 모두 닫고 다시 실행합니다.
- `Codex CLI was not found`: Codex CLI 또는 OpenAI Codex VS Code 확장을 설치합니다.
- `API 키 방식으로 로그인`: 터미널에서 `codex logout`, `codex login`을 차례로 실행하고 ChatGPT 로그인을 선택합니다.
- Drive 목록이 없음: Google Drive 데스크톱 앱이 켜져 있는지 확인하거나 직접 업로드합니다.
