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
$icon = Join-Path $root 'CuraStack Software.ico'
$setupWizardJpg = Join-Path $root 'CuraStack Software.jpg'
$mainPy = Join-Path $root 'main.py'
$installerPy = Join-Path $root 'installer\installer.py'
$uninstallerPy = Join-Path $root 'installer\uninstaller.py'
$versionJson = Join-Path $root 'version.json'
$assetsDir = Join-Path $root 'assets'
$distDir = Join-Path $root 'dist'
$buildDir = Join-Path $root 'build'
$releaseDir = Join-Path $root 'release'
$installerExe = Join-Path $releaseDir 'CuraStack Software-Installer.exe'

if (-not (Test-Path $python)) {
    throw 'No runnable Python virtual environment found. Create .venv311 or .venv before building.'
}

$pyVersionRaw = & $python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$pyVersion = [version]$pyVersionRaw
if ($pyVersion.Major -eq 3 -and $pyVersion.Minor -ge 13) {
    throw "Unsupported build Python version $pyVersionRaw. Use Python 3.11/3.12 for stable PyInstaller runtime."
}

Remove-Item $buildDir, $distDir, $releaseDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
New-Item -ItemType Directory -Force -Path $buildDir   | Out-Null

# ── Read version and generate Windows EXE metadata files ──────────────────────
$verData    = Get-Content $versionJson -Raw | ConvertFrom-Json
$verMajor   = [int]$verData.major
$verMinor   = [int]$verData.minor
$verPatch   = [int]$verData.patch
$verBuild   = [int]$verData.build
$verStr     = "$verMajor.$verMinor.$verPatch.$verBuild"
$verTuple   = "($verMajor, $verMinor, $verPatch, $verBuild)"
$copyYear   = if ((Get-Date).Year -gt 2025) { "2025-$((Get-Date).Year)" } else { "2025" }

function New-VersionInfoFile {
    param(
        [string]$FilePath,
        [string]$FileDescription,
        [string]$OriginalFilename,
        [string]$VersionTuple,
        [string]$VersionStr,
        [string]$CopyYear
    )
    @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=$VersionTuple,
    prodvers=$VersionTuple,
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'CuraStack Software'),
        StringStruct(u'FileDescription', u'$FileDescription'),
        StringStruct(u'FileVersion', u'$VersionStr'),
        StringStruct(u'InternalName', u'$OriginalFilename'),
        StringStruct(u'LegalCopyright', u'Copyright $CopyYear CuraStack Software'),
        StringStruct(u'OriginalFilename', u'$OriginalFilename'),
        StringStruct(u'ProductName', u'CuraStack Software'),
        StringStruct(u'ProductVersion', u'$VersionStr')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"@ | Set-Content -Path $FilePath -Encoding UTF8
}

$appVerFile         = Join-Path $buildDir 'version_info_app.txt'
$installerVerFile   = Join-Path $buildDir 'version_info_installer.txt'
$uninstallerVerFile = Join-Path $buildDir 'version_info_uninstaller.txt'

New-VersionInfoFile -FilePath $appVerFile -FileDescription 'CuraStack Software - Practice Management' `
    -OriginalFilename 'CuraStack Software.exe' -VersionTuple $verTuple -VersionStr $verStr -CopyYear $copyYear
New-VersionInfoFile -FilePath $installerVerFile -FileDescription 'CuraStack Software Installer' `
    -OriginalFilename 'CuraStack Software-Installer.exe' -VersionTuple $verTuple -VersionStr $verStr -CopyYear $copyYear
New-VersionInfoFile -FilePath $uninstallerVerFile -FileDescription 'CuraStack Software Uninstaller' `
    -OriginalFilename 'CuraStack Software Uninstaller.exe' -VersionTuple $verTuple -VersionStr $verStr -CopyYear $copyYear

Write-Host "EXE version metadata files generated for v$verStr."

$pyInstallerArgs = @(
    '-m', 'PyInstaller',
    '--noconfirm',
    '--clean',
    '--windowed',
    '--onedir',
    '--name', 'CuraStack Software',
    '--icon', $icon,
    '--distpath', $distDir,
    '--workpath', (Join-Path $buildDir 'app'),
    '--specpath', $buildDir,
    '--add-data', ($assetsDir + ';assets'),
    '--hidden-import', 'pypdf',
    '--hidden-import', 'pypdf.generic',
    '--collect-all', 'pypdf',
    '--hidden-import', 'fitz',
    '--collect-all', 'fitz',
    '--hidden-import', 'PIL',
    '--hidden-import', 'PIL.Image',
    '--hidden-import', 'PIL.ImageTk',
    '--collect-all', 'PIL',
    '--hidden-import', 'cms_pdf',
    '--hidden-import', 'migration',
    '--hidden-import', 'dsm_codes',
    '--hidden-import', 'cryptography',
    '--collect-all', 'cryptography',
    '--collect-all', 'cffi',
    '--version-file', $appVerFile,
    $mainPy
)

& $python @pyInstallerArgs

# Copy version.json to the app dist folder so the standalone dist build knows its version.
$versionJsonDest = Join-Path $distDir 'CuraStack Software\version.json'
Copy-Item $versionJson $versionJsonDest -Force
Write-Host "Copied version.json to dist."

# Copy app icon into the app dist folder so runtime icon loading can find it.
$iconDest = Join-Path $distDir 'CuraStack Software\CuraStack Software.ico'
Copy-Item $icon $iconDest -Force
Write-Host "Copied CuraStack Software.ico to dist."

# Copy setup JPG into the app dist folder so updater dialogs can show the same artwork.
if (Test-Path $setupWizardJpg) {
    $setupJpgDest = Join-Path $distDir 'CuraStack Software\CuraStack Software.jpg'
    Copy-Item $setupWizardJpg $setupJpgDest -Force
    Write-Host "Copied CuraStack Software.jpg to dist."
}

# Copy CMS-1500 fillable template into the app dist folder so it ships with the installer.
$cmsTemplate = Join-Path $root 'CMS1500_template.pdf'
$cmsTemplateDest = Join-Path $distDir 'CuraStack Software\CMS1500_template.pdf'
if (Test-Path $cmsTemplate) {
    Copy-Item $cmsTemplate $cmsTemplateDest -Force
    Write-Host "Copied CMS1500_template.pdf to dist."
} else {
    Write-Warning "CMS1500_template.pdf not found at path: $cmsTemplate. Installer will ship without it."
}

$cmsBackTemplates = @(
    (Join-Path $root 'CMS1500_template_back.pdf'),
    (Join-Path $root 'CMS 1500_templete_back.pdf')
)
$cmsBackTemplate = $cmsBackTemplates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($cmsBackTemplate) {
    $cmsBackTemplateDest = Join-Path $distDir ('CuraStack Software\' + (Split-Path $cmsBackTemplate -Leaf))
    Copy-Item $cmsBackTemplate $cmsBackTemplateDest -Force
    Write-Host "Copied $(Split-Path $cmsBackTemplate -Leaf) to dist."
}

$uninstallerArgs = @(
    '-m', 'PyInstaller',
    '--noconfirm',
    '--clean',
    '--windowed',
    '--onefile',
    '--name', 'CuraStack Software Uninstaller',
    '--icon', $icon,
    '--distpath', $distDir,
    '--workpath', (Join-Path $buildDir 'uninstaller'),
    '--specpath', $buildDir,
    '--version-file', $uninstallerVerFile,
    $uninstallerPy
)

& $python @uninstallerArgs

$installerArgs = @(
    '-m', 'PyInstaller',
    '--noconfirm',
    '--clean',
    '--windowed',
    '--onefile',
    '--name', 'CuraStack Software-Installer',
    '--icon', $icon,
    '--distpath', $releaseDir,
    '--workpath', (Join-Path $buildDir 'installer'),
    '--specpath', $buildDir,
    '--add-data', ((Join-Path $distDir 'CuraStack Software') + ';app'),
    '--add-data', ((Join-Path $distDir 'CuraStack Software Uninstaller.exe') + ';.'),
    '--add-data', ($icon + ';.'),
    '--add-data', ($versionJson + ';.'),
    '--version-file', $installerVerFile
)

if (Test-Path $setupWizardJpg) {
    $installerArgs += @('--add-data', ($setupWizardJpg + ';.'))
    Write-Host "Including setup wizard image: CuraStack Software.jpg"
} else {
    Write-Warning "CuraStack Software.jpg not found at repo root; setup wizard will use fallback header design."
}

$installerArgs += $installerPy

& $python @installerArgs

Write-Host "Installer created at: $installerExe"