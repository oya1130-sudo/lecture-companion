$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$distRoot = Join-Path $projectRoot 'dist'
$packageName = 'lecture-companion-windows-0.2.0'
$packageRoot = Join-Path $distRoot $packageName
$zipPath = Join-Path $distRoot "$packageName.zip"
$hashPath = Join-Path $distRoot "$packageName.sha256.txt"

function Assert-SafeBuildPath([string]$Path) {
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $fullDist = [System.IO.Path]::GetFullPath($distRoot)
    if (-not $fullPath.StartsWith($fullDist + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "빌드 대상이 dist 폴더 밖입니다: $fullPath"
    }
}

New-Item -ItemType Directory -Path $distRoot -Force | Out-Null
foreach ($oldPath in @($packageRoot, $zipPath, $hashPath)) {
    Assert-SafeBuildPath $oldPath
    if (Test-Path -LiteralPath $oldPath) {
        Remove-Item -LiteralPath $oldPath -Recurse -Force
    }
}

New-Item -ItemType Directory -Path $packageRoot | Out-Null

$rootFiles = @(
    '.env.example',
    'app.py',
    'config.example.yaml',
    'CONTRIBUTING.md',
    'default-guides.example.yaml',
    'pyproject.toml',
    'QUICKSTART.md',
    'README.md',
    'run.ps1',
    'SECURITY.md',
    'start-app.cmd'
)
foreach ($relativePath in $rootFiles) {
    $source = Join-Path $projectRoot $relativePath
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "배포 필수 파일이 없습니다: $relativePath"
    }
    Copy-Item -LiteralPath $source -Destination (Join-Path $packageRoot $relativePath)
}

foreach ($relativeDirectory in @('src\prestudy', 'tests', 'docs')) {
    $sourceDirectory = Join-Path $projectRoot $relativeDirectory
    $targetDirectory = Join-Path $packageRoot $relativeDirectory
    New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
    Get-ChildItem -LiteralPath $sourceDirectory -File |
        Where-Object { $_.Extension -in @('.py', '.md') } |
        ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $targetDirectory }
}

$forbiddenNames = @(
    'credentials.json',
    'token.json',
    'default-guides.yaml',
    'sample-input.yaml',
    'config.yaml'
)
$packagedFiles = Get-ChildItem -LiteralPath $packageRoot -Recurse -File
$unsafeFiles = $packagedFiles | Where-Object {
    $_.Extension -eq '.pdf' -or $_.Name -in $forbiddenNames
}
if ($unsafeFiles) {
    throw "개인 자료 또는 인증 파일이 배포본에 포함됐습니다: $($unsafeFiles.FullName -join ', ')"
}

$textFiles = $packagedFiles | Where-Object {
    $_.Extension -in @('.py', '.ps1', '.cmd', '.md', '.toml', '.yaml', '.yml', '.example')
}
$personalMatches = $textFiles | Select-String -Pattern '(?i)C:\\Users\\[^\\\s]+'
if ($personalMatches) {
    throw "개인 경로가 배포본에 남아 있습니다: $($personalMatches.Path | Select-Object -Unique)"
}

Compress-Archive -LiteralPath $packageRoot -DestinationPath $zipPath -CompressionLevel Optimal
$hash = Get-FileHash -LiteralPath $zipPath -Algorithm SHA256
"$($hash.Hash.ToLowerInvariant())  $([System.IO.Path]::GetFileName($zipPath))" |
    Set-Content -LiteralPath $hashPath -Encoding ASCII

Write-Host "배포 ZIP 생성 완료: $zipPath"
Write-Host "SHA-256: $($hash.Hash.ToLowerInvariant())"
