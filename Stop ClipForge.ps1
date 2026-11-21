$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcherDirectory = Join-Path $env:LOCALAPPDATA "ClipForgeAI\launcher"

function Stop-ClipForgeProcess([string]$pidFile, [string]$processName, [string]$expectedArgument) {
    $pidPath = Join-Path $launcherDirectory $pidFile
    if (-not (Test-Path -LiteralPath $pidPath -PathType Leaf)) { return }

    $targetProcessId = 0
    if ([int]::TryParse((Get-Content -LiteralPath $pidPath -Raw).Trim(), [ref]$targetProcessId)) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $targetProcessId" -ErrorAction SilentlyContinue
        if ($process -and $process.Name -ieq $processName -and $process.CommandLine.Contains($expectedArgument)) {
            Stop-Process -Id $targetProcessId -Force -ErrorAction SilentlyContinue
        }
    }
    Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
}

Stop-ClipForgeProcess "frontend.pid" "node.exe" (Join-Path $projectRoot "frontend\node_modules\vite\bin\vite.js")
Stop-ClipForgeProcess "backend.pid" "python.exe" (Join-Path $projectRoot "backend")

Add-Type -AssemblyName PresentationFramework
[System.Windows.MessageBox]::Show("ClipForge's frontend and backend have been stopped.", "ClipForge AI", "OK", "Information") | Out-Null
