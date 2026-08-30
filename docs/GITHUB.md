# GitHub로 구조 공유하기

## 공개 전 결정

- 저장소 이름
- 공개 또는 비공개
- 공개 저장소라면 라이선스(MIT, Apache-2.0 등)

라이선스가 없으면 다른 사람이 코드를 볼 수는 있지만 일반적인 재사용·수정 권한이 명확하지 않습니다.

## 로컬 준비

```powershell
git init
git status --short
git add .
git diff --cached --check
git status --short
git commit -m "Initial release"
git branch -M main
```

`git status`에 PDF, `data`, `output`, 캐시, 토큰, 개인 설정 파일이 보이면 커밋하지 말고 `.gitignore`를 먼저 수정합니다.

## 원격 저장소 연결

GitHub에서 빈 저장소를 만든 뒤 표시되는 주소를 사용합니다.

```powershell
git remote add origin https://github.com/USERNAME/REPOSITORY.git
git push -u origin main
```

GitHub CLI를 사용한다면 로그인 후 다음과 같은 흐름도 가능합니다.

```powershell
gh auth login
gh repo create REPOSITORY --private --source . --remote origin --push
```

검증이 끝난 뒤 공개하려면 GitHub 저장소 설정에서 visibility를 변경합니다. 처음에는 비공개 저장소를 권장합니다.

## 배포 ZIP 게시

`build-share-package.ps1`로 만든 ZIP과 SHA-256 파일을 GitHub Releases에 첨부합니다. 소스 저장소와 사용자용 ZIP을 분리하면 받는 사람은 Git을 몰라도 사용할 수 있습니다.
