param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('summed')]
    [string]$Program
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($env:SUMMED_HOME)) {
    $env:SUMMED_HOME = Join-Path $PSScriptRoot '.summed-data'
}

try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
}
catch {
    # Console encoding is cosmetic; startup can continue if it cannot change.
}

$displayName = 'summed'
$entrypoint = Join-Path $PSScriptRoot 'app.py'
$port = 8502
$bindAddress = '127.0.0.1'
$browserAddress = 'localhost'
$localAppUrl = "http://${browserAddress}:${port}"
$healthUrl = "http://127.0.0.1:${port}/_stcore/health"

function Test-AppHealth {
    param([int]$Attempts = 1)

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                return $true
            }
        }
        catch {
            if ($attempt -lt $Attempts) {
                Start-Sleep -Milliseconds 500
            }
        }
    }
    return $false
}

function Open-AppBrowser {
    param([Parameter(Mandatory = $true)][string]$Url)

    try {
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = $Url
        $startInfo.UseShellExecute = $true
        [System.Diagnostics.Process]::Start($startInfo) | Out-Null
        return
    }
    catch {
        $explorer = Join-Path $env:WINDIR 'explorer.exe'
        if (Test-Path -LiteralPath $explorer) {
            & $explorer $Url
            if ($LASTEXITCODE -eq 0) {
                return
            }
        }
        throw "브라우저를 자동으로 열지 못했습니다. 주소창에 $Url 을 입력해 주세요."
    }
}

if (Test-AppHealth -Attempts 4) {
    Write-Host '이미 실행 중인 summed를 브라우저에서 엽니다.'
    Open-AppBrowser -Url $localAppUrl
    return
}

function Set-DriveSourceFromShortcut {
    param(
        [Parameter(Mandatory = $true)][string]$EnvironmentName,
        [Parameter(Mandatory = $true)][string]$ShortcutName
    )

    if (-not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($EnvironmentName, 'Process'))) {
        return
    }
    try {
        $shell = New-Object -ComObject WScript.Shell
        foreach ($drive in Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue) {
            $shortcutPath = Join-Path $drive.Root "내 드라이브\${ShortcutName}.lnk"
            if (-not (Test-Path -LiteralPath $shortcutPath -PathType Leaf)) {
                continue
            }
            $targetPath = $shell.CreateShortcut($shortcutPath).TargetPath
            if (-not [string]::IsNullOrWhiteSpace($targetPath) -and (Test-Path -LiteralPath $targetPath -PathType Container)) {
                [Environment]::SetEnvironmentVariable($EnvironmentName, $targetPath, 'Process')
                Write-Host "Google Drive 자료 연결: $ShortcutName"
                return
            }
        }
    }
    catch {
        # Python의 보조 탐색이 있으므로 바로가기 조회 실패만으로 실행을 중단하지 않습니다.
    }
}

Set-DriveSourceFromShortcut -EnvironmentName 'SUMMED_SUMMARY_ROOT' -ShortcutName '00 학습자료'
Set-DriveSourceFromShortcut -EnvironmentName 'SUMMED_TRANSCRIPT_ROOT' -ShortcutName '녹음부'

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
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$venvReady = Join-Path $PSScriptRoot '.venv\.summed-ready'
$dependencyFingerprint = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'pyproject.toml') -Algorithm SHA256).Hash
$savedFingerprint = ''
if (Test-Path -LiteralPath $venvReady) {
    $savedFingerprint = (Get-Content -LiteralPath $venvReady -Raw -ErrorAction SilentlyContinue).Trim()
}

if (-not (Test-Path -LiteralPath $venvPython) -or $savedFingerprint -ne $dependencyFingerprint) {
    Write-Host '프로그램 실행 환경을 준비합니다. 최초 실행에는 몇 분 정도 걸릴 수 있습니다.'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        & $basePythonCommand -m venv (Join-Path $PSScriptRoot '.venv')
    }
    & $venvPython -m pip install -e $PSScriptRoot
    if ($LASTEXITCODE -ne 0) {
        throw '필요한 Python 패키지 설치에 실패했습니다.'
    }
    Set-Content -LiteralPath $venvReady -Value $dependencyFingerprint -Encoding ASCII
}

$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = 'false'
Write-Host "${displayName}를 시작합니다: $localAppUrl"
$workDirectory = $env:SUMMED_HOME
New-Item -ItemType Directory -Path $workDirectory -Force | Out-Null
$stdoutLog = Join-Path $workDirectory 'streamlit.stdout.log'
$stderrLog = Join-Path $workDirectory 'streamlit.stderr.log'
$quotedEntrypoint = '"' + $entrypoint + '"'
$streamlitArgs = @(
    '-m', 'streamlit', 'run', $quotedEntrypoint,
    '--browser.gatherUsageStats', 'false',
    '--browser.serverAddress', $browserAddress,
    '--server.headless', 'true',
    '--server.showEmailPrompt', 'false',
    '--server.address', $bindAddress,
    '--server.port', "$port",
    '--server.maxUploadSize', '500',
    '--server.maxMessageSize', '500',
    '--server.websocketPingInterval', '20'
)

$serverProcess = Start-Process `
    -FilePath $venvPython `
    -ArgumentList $streamlitArgs `
    -WorkingDirectory $PSScriptRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru

$deadline = (Get-Date).AddSeconds(60)
while ((Get-Date) -lt $deadline) {
    if (Test-AppHealth) {
        Write-Host "summed 주소: $localAppUrl"
        Open-AppBrowser -Url $localAppUrl
        return
    }
    if ($serverProcess.HasExited) {
        $errorTail = ''
        if (Test-Path -LiteralPath $stderrLog) {
            $errorTail = (Get-Content -LiteralPath $stderrLog -Tail 20 -ErrorAction SilentlyContinue) -join [Environment]::NewLine
        }
        throw "summed 서버가 시작 중 종료되었습니다.$([Environment]::NewLine)$errorTail"
    }
    Start-Sleep -Milliseconds 500
}

if (-not $serverProcess.HasExited) {
    Stop-Process -Id $serverProcess.Id -Force -ErrorAction SilentlyContinue
}
throw "summed 서버가 60초 안에 준비되지 않았습니다. 로그를 확인해 주세요: $stderrLog"
