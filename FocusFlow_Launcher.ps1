# FocusFlow Launcher
$packagePath = "$env:TEMP\FocusFlow_Package"
$zipPath = Join-Path $PSScriptRoot "FocusFlow_Standalone.zip"

# Extract if not already
if (-not (Test-Path $packagePath)) {
    Expand-Archive -Path $zipPath -DestinationPath $env:TEMP -Force
}

# Run the app
$batPath = Join-Path $packagePath "FocusFlow.bat"
Start-Process -FilePath $batPath -WorkingDirectory $packagePath
