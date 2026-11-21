$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDirectory = Join-Path $projectRoot "backend"
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$node = (Get-Command node.exe -ErrorAction SilentlyContinue).Source
$viteEntry = Join-Path $projectRoot "frontend\node_modules\vite\bin\vite.js"
$launcherDirectory = Join-Path $env:LOCALAPPDATA "ClipForgeAI\launcher"
$outputDirectory = "D:\Clip Forge"
$apiUrl = "http://127.0.0.1:8000/api/health"
$frontendUrl = "http://127.0.0.1:5173"

function Show-StartupError([string]$message) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show($message, "ClipForge AI", "OK", "Error") | Out-Null
}

function Test-Service([string]$url) {
    try {
        $null = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
        return $true
    }
    catch {
        return $false
    }
}

try {
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw "Python environment not found:`n$python`n`nRun the project setup commands in INSTALLATION.md first."
    }
    if (-not $node -or -not (Test-Path -LiteralPath $viteEntry -PathType Leaf)) {
        throw "Node.js or frontend dependencies are missing.`nInstall Node.js, then run: npm --prefix frontend install"
    }

    New-Item -ItemType Directory -Path $launcherDirectory -Force | Out-Null
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    $env:PYTHONPATH = $backendDirectory
    $env:CLIPFORGE_OUTPUT_DIR = $outputDirectory

    if (-not (Test-Service $apiUrl)) {
        $apiProcess = Start-Process -FilePath $python `
            -ArgumentList "-m uvicorn clipforge.main:app --app-dir `"$backendDirectory`" --host 127.0.0.1 --port 8000" `
            -WorkingDirectory $projectRoot `
            -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $launcherDirectory "backend.log") `
            -RedirectStandardError (Join-Path $launcherDirectory "backend-error.log") `
            -PassThru
        Set-Content -LiteralPath (Join-Path $launcherDirectory "backend.pid") -Value $apiProcess.Id
    }

    if (-not (Test-Service $frontendUrl)) {
        $frontendProcess = Start-Process -FilePath $node `
            -ArgumentList "`"$viteEntry`" --host 127.0.0.1 --port 5173 --strictPort" `
            -WorkingDirectory (Join-Path $projectRoot "frontend") `
            -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $launcherDirectory "frontend.log") `
            -RedirectStandardError (Join-Path $launcherDirectory "frontend-error.log") `
            -PassThru
        Set-Content -LiteralPath (Join-Path $launcherDirectory "frontend.pid") -Value $frontendProcess.Id
    }

    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if ((Test-Service $apiUrl) -and (Test-Service $frontendUrl)) {
            $ready = $true
            break
        }
        Start-Sleep -Milliseconds 750
    }

    if (-not $ready) {
        throw "ClipForge did not start in time. Check logs in:`n$launcherDirectory"
    }

    Start-Process -FilePath $frontendUrl
}
catch {
    Show-StartupError $_.Exception.Message
}
