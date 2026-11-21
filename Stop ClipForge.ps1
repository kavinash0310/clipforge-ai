$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcherDirectory = Join-Path $env:LOCALAPPDATA "ClipForgeAI\launcher"

function Stop-ClipForgeProcess([string]$pidFile, [string]$processName, [string]$expectedArgument) {
    $pidPath = Join-Path $launcherDirectory $pidFile
    $targetProcessIds = [System.Collections.Generic.HashSet[int]]::new()

    if (Test-Path -LiteralPath $pidPath -PathType Leaf) {
        $savedProcessId = 0
        if ([int]::TryParse((Get-Content -LiteralPath $pidPath -Raw).Trim(), [ref]$savedProcessId)) {
            [void]$targetProcessIds.Add($savedProcessId)
        }
    }

    Get-CimInstance Win32_Process -Filter "Name = '$processName'" -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.CommandLine -and $_.CommandLine.Contains($expectedArgument)) {
            [void]$targetProcessIds.Add([int]$_.ProcessId)
        }
    }

    foreach ($targetProcessId in $targetProcessIds) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $targetProcessId" -ErrorAction SilentlyContinue
        if ($process -and $process.Name -ieq $processName -and $process.CommandLine -and $process.CommandLine.Contains($expectedArgument)) {
            Stop-Process -Id $targetProcessId -Force -ErrorAction SilentlyContinue
        }
    }

    Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
}

Stop-ClipForgeProcess "frontend.pid" "node.exe" (Join-Path $projectRoot "frontend\node_modules\vite\bin\vite.js")
Stop-ClipForgeProcess "backend.pid" "python.exe" (Join-Path $projectRoot "backend")

Add-Type -AssemblyName PresentationFramework
[System.Windows.MessageBox]::Show("ClipForge's frontend and backend have been stopped.", "ClipForge AI", "OK", "Information") | Out-Null
