param(
    [Parameter(Mandatory=$true)][string]$QtDir,
    [string]$Generator = "Visual Studio 17 2022",
    [switch]$Installer,
    [string]$Iscc = "ISCC.exe"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Executable failed with exit code $LASTEXITCODE" }
}
if ([Environment]::OSVersion.Platform -ne "Win32NT") { throw "Build Windows packages on Windows x64." }
$QtDir = (Resolve-Path $QtDir).Path
$DeployQt = Join-Path $QtDir "bin\windeployqt.exe"
if (!(Test-Path $DeployQt) -or !(Test-Path (Join-Path $QtDir "lib\cmake\Qt6PdfWidgets"))) {
    throw "QtDir must point to a Qt 6 x64 kit with Qt PDF and PdfWidgets."
}
$PreviousPath = $env:PATH
$PreviousHome = $env:PAPER_TRANSLATOR_HOME
$PreviousPython = $env:PAPER_TEST_PYTHON
$TestHome = Join-Path ([IO.Path]::GetTempPath()) ("PaperTranslator-Qt-build-" + [guid]::NewGuid())
Push-Location $Root
try {
    $env:PATH = (Join-Path $QtDir "bin") + ";" + $PreviousPath
    $env:PAPER_TRANSLATOR_HOME = $TestHome
    if (!(Test-Path ".venv\Scripts\python.exe")) { Invoke-Checked "py" @("-3.12", "-m", "venv", ".venv") }
    $Python = Join-Path $Root ".venv\Scripts\python.exe"
    $env:PAPER_TEST_PYTHON = $Python
    Invoke-Checked $Python @("-m", "pip", "install", "-r", "requirements-build.txt")
    Invoke-Checked $Python @("scripts\test-engine.py")
    $CmakeArgs = @("-S", ".", "-B", "build-windows", "-G", $Generator,
                   "-DCMAKE_PREFIX_PATH=$QtDir", "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_TESTING=ON")
    if ($Generator -like "Visual Studio*") { $CmakeArgs += @("-A", "x64") }
    Invoke-Checked "cmake" $CmakeArgs
    Invoke-Checked "cmake" @("--build", "build-windows", "--config", "Release", "--parallel")
    Invoke-Checked "ctest" @("--test-dir", "build-windows", "-C", "Release", "--output-on-failure")
    Invoke-Checked $Python @("-m", "PyInstaller", "--clean", "--noconfirm", "--workpath", "build-engine", "packaging\engine.spec")
    $Stage = Join-Path $Root "dist\PaperTranslator"
    if (Test-Path $Stage) { Move-Item $Stage ($Stage + ".previous-" + [guid]::NewGuid()) }
    New-Item -ItemType Directory -Force $Stage | Out-Null
    $NativeExe = Join-Path $Root "build-windows\Release\PaperTranslator.exe"
    if (!(Test-Path $NativeExe)) { $NativeExe = Join-Path $Root "build-windows\PaperTranslator.exe" }
    Copy-Item $NativeExe $Stage
    $EngineStage = Join-Path $Stage "engine"
    Copy-Item "dist\pdfmathtranslate-engine" $EngineStage -Recurse
    Invoke-Checked $DeployQt @("--release", "--compiler-runtime", "--no-translations", "--dir", $Stage, (Join-Path $Stage "PaperTranslator.exe"))
    if (!(Test-Path (Join-Path $Stage "sqldrivers\qsqlite.dll"))) { throw "Qt SQLite plugin is missing." }
    if (!(Test-Path (Join-Path $Stage "Qt6Pdf.dll"))) { throw "Qt PDF runtime is missing." }
    Copy-Item "README.md" $Stage
    foreach ($Program in @((Join-Path $EngineStage "pdfmathtranslate-engine.exe"), (Join-Path $Stage "PaperTranslator.exe"))) {
        $Argument = if ($Program -like "*pdfmathtranslate-engine.exe") { "--probe" } else { "--smoke-test" }
        $Run = Start-Process -FilePath $Program -ArgumentList $Argument -Wait -PassThru
        if ($Run.ExitCode -ne 0) { throw "Packaged check failed: $Program. Logs: $TestHome\logs" }
    }
    $Zip = Join-Path $Root "dist\PaperTranslator-Qt-windows-x64.zip"
    Compress-Archive -Path $Stage -DestinationPath $Zip -Force
    if ($Installer) { Invoke-Checked $Iscc @("packaging\installer.iss") }
    Write-Host "Built: $Zip"
    Write-Host "Run: $Stage\PaperTranslator.exe"
} finally {
    $env:PATH = $PreviousPath
    $env:PAPER_TRANSLATOR_HOME = $PreviousHome
    $env:PAPER_TEST_PYTHON = $PreviousPython
    Pop-Location
}
