$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($env:PRESTUDY_HOME)) {
    $env:PRESTUDY_HOME = $PSScriptRoot
}

try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
}
catch {
    # Console encoding is cosmetic; startup can continue if it cannot change.
}

function Find-CodexCommand {
    $existing = Get-Command codex.exe -ErrorAction SilentlyContinue
    if ($existing) {
        return $existing.Source
    }

    $candidates = @()
    $extensionRoots = @(
        (Join-Path $env:USERPROFILE '.vscode\extensions'),
        (Join-Path $env:USERPROFILE '.vscode-insiders\extensions')
    )
    foreach ($root in $extensionRoots) {
        if (-not (Test-Path -LiteralPath $root)) {
            continue
        }
        foreach ($extension in Get-ChildItem -LiteralPath $root -Directory -Filter 'openai.chatgpt-*' -ErrorAction SilentlyContinue) {
            $candidate = Join-Path $extension.FullName 'bin\windows-x86_64\codex.exe'
            if (Test-Path -LiteralPath $candidate) {
                $candidates += Get-Item -LiteralPath $candidate
            }
        }
    }
    $latest = $candidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latest) {
        return $latest.FullName
    }

    $npmCommand = Join-Path $env:APPDATA 'npm\codex.cmd'
    if (Test-Path -LiteralPath $npmCommand) {
        return $npmCommand
    }
    throw 'Codex CLI was not found. Install or enable the OpenAI Codex VS Code extension.'
}

function Find-PythonCommand {
    foreach ($name in @('py.exe', 'python.exe')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $command) {
            continue
        }
        $previousPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            & $command.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                return $command.Source
            }
        }
        finally {
            $ErrorActionPreference = $previousPreference
        }
    }
    throw 'Python 3.11 이상이 필요합니다. https://www.python.org/downloads/windows/ 에서 설치한 뒤 다시 실행해 주세요.'
}

$codexCommand = Find-CodexCommand
$codexDirectory = Split-Path -Parent $codexCommand
if ($env:PATH -notlike "*$codexDirectory*") {
    $env:PATH = "$codexDirectory;$env:PATH"
}

function Get-CodexLoginStatus {
    # Windows PowerShell 5.1 turns native stderr into an ErrorRecord when
    # ErrorActionPreference is Stop. Codex writes its successful login status
    # to stderr, so capture it with Continue and judge by the exit code.
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $statusText = (& $codexCommand login status 2>&1 | Out-String)
        $statusCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    return [PSCustomObject]@{ Text = $statusText; ExitCode = $statusCode }
}

$loginResult = Get-CodexLoginStatus
if ($loginResult.ExitCode -ne 0) {
    Write-Host 'ChatGPT 구독 계정 로그인이 필요합니다. 브라우저 로그인을 시작합니다.'
    & $codexCommand login
    $loginResult = Get-CodexLoginStatus
}
if ($loginResult.Text -notmatch 'ChatGPT') {
    throw '현재 Codex가 API 키 방식으로 로그인되어 있습니다. codex logout 후 codex login으로 ChatGPT 계정에 로그인해 주세요.'
}

$basePythonCommand = Find-PythonCommand
$pythonCommand = $basePythonCommand
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$venvReady = Join-Path $PSScriptRoot '.venv\.lecture-companion-ready'
$pyprojectPath = Join-Path $PSScriptRoot 'pyproject.toml'
$dependencyFingerprint = (Get-FileHash -LiteralPath $pyprojectPath -Algorithm SHA256).Hash
$savedFingerprint = ''
if (Test-Path -LiteralPath $venvReady) {
    $savedFingerprint = (Get-Content -LiteralPath $venvReady -Raw -ErrorAction SilentlyContinue).Trim()
}

if ((Test-Path -LiteralPath $venvPython) -and ($savedFingerprint -eq $dependencyFingerprint)) {
    $pythonCommand = $venvPython
}
else {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $basePythonCommand -c "import pathlib, sys, streamlit, prestudy; root = pathlib.Path(sys.argv[1]).resolve(); raise SystemExit(0 if pathlib.Path(prestudy.__file__).resolve().is_relative_to(root) else 1)" $PSScriptRoot 2>&1 | Out-Null
        $globalEnvironmentReady = $LASTEXITCODE -eq 0
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }

    if (-not $globalEnvironmentReady) {
        Write-Host '최초 실행에 필요한 패키지를 설치합니다. 몇 분 정도 걸릴 수 있습니다.'
        if (-not (Test-Path -LiteralPath $venvPython)) {
            & $basePythonCommand -m venv (Join-Path $PSScriptRoot '.venv')
        }
        & $venvPython -m pip install -e $PSScriptRoot
        if ($LASTEXITCODE -ne 0) {
            throw '필요한 Python 패키지 설치에 실패했습니다.'
        }
        Set-Content -LiteralPath $venvReady -Value $dependencyFingerprint -Encoding ASCII
        $pythonCommand = $venvPython
    }
}

$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = 'false'
$lanAddress = 'localhost'
try {
    $networkConfiguration = Get-NetIPConfiguration -ErrorAction Stop |
        Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } |
        Select-Object -First 1
    $detectedAddress = $networkConfiguration.IPv4Address.IPAddress | Select-Object -First 1
    if ($detectedAddress) {
        $lanAddress = $detectedAddress
    }
}
catch {
    # Local use still works when Windows cannot determine the LAN address.
}

Write-Host "Tablet URL (same Wi-Fi): http://${lanAddress}:8501"
& $pythonCommand -m streamlit run (Join-Path $PSScriptRoot 'app.py') `
    --browser.gatherUsageStats false `
    --browser.serverAddress $lanAddress `
    --server.headless false `
    --server.showEmailPrompt false `
    --server.address 0.0.0.0 `
    --server.port 8501 `
    --server.maxUploadSize 500 `
    --server.maxMessageSize 500 `
    --server.websocketPingInterval 20
