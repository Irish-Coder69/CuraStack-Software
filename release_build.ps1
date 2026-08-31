param(
    [string]$CommitMessage,
    [string]$ReleaseNotes,
    [switch]$SkipBuild,
    [switch]$SkipPush,
    [switch]$SkipRelease,
    [switch]$AllowDirty,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = $null
$pythonCandidates = @(
    (Join-Path $root '.venv311\Scripts\python.exe'),
    (Join-Path $root '.venv\Scripts\python.exe')
)
foreach ($candidate in $pythonCandidates) {
    if (-not (Test-Path $candidate)) {
        continue
    }
    try {
        $probe = & $candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($LASTEXITCODE -eq 0 -and $probe -match '^\d+\.\d+$') {
            $python = $candidate
            break
        }
    } catch {
        continue
    }
}
$versionJson = Join-Path $root 'version.json'
$installerExe = Join-Path $root 'release\CuraStack Software-Installer.exe'

if (-not (Test-Path $python)) {
    throw 'No runnable Python virtual environment found (.venv311 or .venv).'
}

function Invoke-Step {
    param(
        [string]$Title,
        [scriptblock]$Action
    )
    Write-Host "`n==> $Title" -ForegroundColor Cyan
    if ($DryRun) {
        Write-Host 'DRY RUN: skipped.' -ForegroundColor Yellow
        return
    }
    & $Action
}

Push-Location $root
try {
    if (-not $AllowDirty) {
        $status = git status --porcelain
        if ($status) {
            throw "Working tree is not clean. Commit/stash changes first, or rerun with -AllowDirty."
        }
    }

    Invoke-Step 'Bump build version' {
        & $python bump_version.py build | Out-Host
    }

    if (-not (Test-Path $versionJson)) {
        throw "version.json not found at: $versionJson"
    }

    $version = Get-Content $versionJson -Raw | ConvertFrom-Json
    $versionTag = "v$($version.major).$($version.minor).$($version.patch)-build$($version.build)"
    $versionTitle = "CuraStack Software v$($version.major).$($version.minor).$($version.patch) Build $($version.build)"

    if (-not $CommitMessage) {
        $CommitMessage = "Build $($version.build): automated release"
    }

    if (-not $ReleaseNotes) {
        $ReleaseNotes = @"
## What's Changed

### Automation
- Automated build/release generated with release_build.ps1

### Version
- Build bumped to $($version.major).$($version.minor).$($version.patch) Build $($version.build)
"@
    }

    Invoke-Step 'Quick syntax check' {
        & $python -m py_compile main.py cms_pdf.py database.py
    }

    if (-not $SkipBuild) {
        Invoke-Step 'Build installer' {
            powershell -ExecutionPolicy RemoteSigned -File .\build_installer.ps1
        }

        if (-not $DryRun -and -not (Test-Path $installerExe)) {
            throw "Installer not found at: $installerExe"
        }
    }

    Invoke-Step 'Commit changes' {
        git add version.json
        git add -A
        $pending = git status --porcelain
        if (-not $pending) {
            throw 'No changes to commit after version bump/build.'
        }
        git commit -m $CommitMessage
    }

    if (-not $SkipPush) {
        Invoke-Step 'Push main branch' {
            git push origin main
        }
    }

    if (-not $SkipRelease) {
        Invoke-Step 'Create GitHub release' {
            gh release create $versionTag $installerExe --title $versionTitle --notes $ReleaseNotes --latest
        }
        if (-not $DryRun) {
            Write-Host "Release published: https://github.com/Irish-Coder69/CuraStack-Software/releases/tag/$versionTag" -ForegroundColor Green
        }
    }

    if ($DryRun) {
        Write-Host "`nDry run complete." -ForegroundColor Yellow
    } else {
        Write-Host "`nRelease workflow complete." -ForegroundColor Green
    }
}
finally {
    Pop-Location
}
