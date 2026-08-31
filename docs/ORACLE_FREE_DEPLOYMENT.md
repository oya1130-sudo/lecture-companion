# Oracle Cloud 무료 배포

Oracle Cloud Infrastructure(OCI)의 Always Free ARM VM 한 대에 앱을 올리는 절차입니다. 현재 무료 한도인 **Ampere A1 2 OCPU·메모리 12GB**를 한 VM에 모두 배정하고, 앱 포트는 인터넷에 공개하지 않은 채 Tailscale로 태블릿에서 접속합니다.

> 이 경로는 소규모 개인 앱과 시험 운영에 적합합니다. Oracle은 7일 동안 CPU·네트워크·메모리 사용률이 모두 낮은 무료 VM을 회수할 수 있으므로, 중요한 자료는 반드시 별도로 백업하세요. 회수를 피하려고 인위적인 부하를 만들지는 않습니다.

## 1. 무료 계정 만들기

1. [Oracle Cloud Free Tier](https://signup.cloud.oracle.com/)에서 계정을 만듭니다.
2. 홈 리전은 **South Korea Central (Seoul), `ap-seoul-1`**을 선택합니다. Always Free 컴퓨트는 홈 리전에서만 만들 수 있고 홈 리전은 나중에 바꾸기 어렵습니다.
3. 본인 확인용 휴대전화와 결제 카드가 필요할 수 있습니다. Oracle 문서상 유료 계정으로 직접 업그레이드하지 않는 한 카드가 청구되지는 않습니다.

서울을 선택하는 이유는 지연 시간이 짧고 A1을 지원하기 때문입니다. **South Korea North (Chuncheon)는 Always Free A1 생성 예외 리전**이므로 선택하지 않습니다.

무료 체험 크레딧이 표시되더라도 아래에서 `Always Free-eligible` 표시가 붙은 자원만 사용하세요. 체험 크레딧은 유료 자원의 비용을 잠시 가릴 수 있습니다.

## 2. 무료 ARM VM 만들기

OCI 콘솔에서 **Compute → Instances → Create instance**로 이동한 뒤 다음처럼 설정합니다.

| 항목 | 설정 |
|---|---|
| Name | `lecture-companion` |
| Image | Ubuntu 24.04 LTS, ARM/aarch64 |
| Shape | `VM.Standard.A1.Flex` |
| OCPU | `2` |
| Memory | `12 GB` |
| Boot volume | 기본 50GB |
| Network | 새 VCN과 public subnet, public IPv4 할당 |
| SSH key | 새 키 생성 후 private key 저장 또는 기존 public key 업로드 |

생성 버튼을 누르기 전에 Shape과 Boot volume에 **Always Free-eligible** 표시가 있는지 확인합니다. 계정 전체 A1 합계가 2 OCPU·12GB를 넘거나 블록 볼륨 합계가 200GB를 넘으면 과금 대상이 될 수 있습니다.

`Out of host capacity`가 나오면 무료 ARM 자리가 일시적으로 없는 것입니다. 설정을 유료 Shape으로 바꾸지 말고 몇 시간 뒤 다시 시도합니다.

### 방화벽

VM의 Security List 또는 Network Security Group 인바운드는 다음만 허용합니다.

- TCP 22: 가능하면 현재 집/학교 공인 IP 한 개(`/32`)에서만 허용
- TCP 8501: **추가하지 않음**
- 그 밖의 앱 포트: 추가하지 않음

Tailscale은 기본적으로 아웃바운드 연결을 이용하므로 8501 인바운드 규칙이 필요 없습니다.

## 3. SSH로 접속

VM 상태가 Running이 되면 표시된 Public IPv4를 복사합니다. Windows Terminal의 PowerShell에서, 내려받은 키와 IP에 맞게 실행합니다.

```powershell
ssh -i .\ssh-key-2026-08-31.key ubuntu@VM_PUBLIC_IP
```

처음 접속할 때 fingerprint 질문에는 콘솔의 IP를 다시 확인한 뒤 `yes`를 입력합니다. 키 파일 권한 오류가 나면 Windows 파일 속성의 보안 탭에서 본인 외 사용자의 읽기 권한을 제거합니다.

## 4. Docker와 Tailscale 설치

VM의 Ubuntu 터미널에서 Docker 공식 저장소를 등록합니다.

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME:-$VERSION_CODENAME} stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"
```

그룹 권한을 적용하기 위해 SSH를 한 번 종료하고 다시 접속합니다.

```bash
exit
```

재접속 후 Docker와 Tailscale을 준비합니다.

```bash
docker --version
docker compose version
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

`tailscale up`이 출력한 주소를 브라우저에서 열어 로그인합니다. 태블릿에도 Tailscale 앱을 설치하고 같은 계정으로 로그인합니다.

## 5. 앱 설치

VM에서 다음을 실행합니다. ARM 첫 빌드는 몇 분 걸릴 수 있습니다.

```bash
git clone https://github.com/oya1130-sudo/lecture-companion.git
cd lecture-companion
cp .env.oracle.example .env
chmod 600 .env
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:8501/_stcore/health
```

Oracle A1은 CPU가 2개이므로 `.env.oracle.example`은 Codex 동시 호출을 1개로 제한합니다. 대기 작업은 큐에 쌓이며, 서버가 버벅이면 자료를 잃는 대신 순서대로 처리합니다.

## 6. Codex 로그인

헤드리스 VM에서는 장치 코드 로그인을 사용합니다.

```bash
docker compose exec app codex login --device-auth
docker compose exec app codex login status
```

첫 명령이 출력한 주소를 개인 브라우저에서 열고 코드를 입력합니다. 로그인 토큰은 `lecture-companion-data` Docker 볼륨에 저장되므로 이 볼륨과 스냅샷을 비밀번호처럼 보호합니다.

## 7. 태블릿용 비공개 HTTPS 주소 만들기

```bash
sudo tailscale serve --bg 8501
tailscale serve status
```

출력된 `https://...ts.net` 주소를 태블릿에서 엽니다. 접속할 때 태블릿의 Tailscale이 켜져 있어야 합니다. **Tailscale Funnel은 사용하지 않습니다.** Funnel은 앱을 공개 인터넷에 노출합니다.

사이드바에도 주소를 표시하려면 `.env`의 빈 값을 채우고 컨테이너를 갱신합니다.

```dotenv
PRESTUDY_PUBLIC_URL=https://서버이름.tailnet이름.ts.net
```

```bash
docker compose up -d
```

## 8. 무료 상태와 백업 확인

OCI 콘솔에서 주기적으로 다음을 확인합니다.

- Shape: `VM.Standard.A1.Flex`, 총 2 OCPU·12GB 이하
- Block/boot volume: 전체 200GB 이하
- 유료 Load Balancer, 추가 public IP, 유료 데이터베이스를 만들지 않았는지
- Billing & Cost Management에서 비용이 0인지

Always Free에는 홈 리전의 블록 볼륨 백업이 최대 5개 포함됩니다. OCI 콘솔에서 Boot volume backup을 만들되, 백업에는 업로드 PDF와 Codex 로그인 토큰이 함께 들어 있음을 기억하세요.

무료 VM이 회수되거나 고장 날 가능성에 대비해 완성 HTML은 작업 후 태블릿이나 Google Drive에 내려받습니다. Oracle의 회수 경고를 받으면 먼저 최신 백업을 만든 뒤 새 무료 인스턴스로 복구합니다.

## 운영 명령

```bash
# 업데이트
git pull --ff-only
docker compose up -d --build

# 상태와 로그
docker compose ps
docker compose logs --tail=100 app

# 재시작
docker compose restart app
```

`docker compose down -v`는 PDF, 결과물, 작업 이력과 Codex 로그인이 든 영구 볼륨까지 삭제하므로 실행하지 않습니다.

## 공식 참고 문서

- [OCI Always Free 자원과 제한](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [OCI Free Tier 계정 안내](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm)
- [OCI 리전 목록](https://docs.oracle.com/en-us/iaas/Content/General/Concepts/regions.htm)
- [Docker Engine Ubuntu 설치](https://docs.docker.com/engine/install/ubuntu/)
- [Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve)
- [Codex CLI](https://learn.chatgpt.com/docs/codex/cli)
