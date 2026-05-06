$ErrorActionPreference = "Stop"

$appName = "DD Manager"
$entryPoint = "dd2.py"
$pythonRoot = python -c "import sys; print(sys.base_prefix)"
$tkDllDir = Join-Path $pythonRoot "DLLs"
$tclRoot = Join-Path $pythonRoot "tcl"
$tkPackageDir = Join-Path $pythonRoot "Lib\\tkinter"
$runtimeHook = "pyi_rth_tk_paths.py"
$distRoot = "dist"
$distAppDir = Join-Path $distRoot $appName
$releaseRoot = "release"
$portableName = "$appName Portable"
$portableDir = Join-Path $releaseRoot $portableName
$portableDataDir = Join-Path $portableDir "$appName Data"
$iconCacheDir = Join-Path $portableDataDir "icon_cache"
$portableZip = Join-Path $releaseRoot "$portableName.zip"
$portableReadme = Join-Path $portableDir "README.md"
$dataReadme = Join-Path $portableDataDir "README.txt"
$iconKeep = Join-Path $iconCacheDir ".keep"

if (-not (Test-Path $entryPoint)) {
    throw "Could not find $entryPoint in the current folder."
}

if (-not (Test-Path $runtimeHook)) {
    throw "Could not find $runtimeHook in the current folder."
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name $appName `
    --hidden-import tkinter `
    --hidden-import _tkinter `
    --runtime-hook $runtimeHook `
    --add-binary "$tkDllDir\\_tkinter.pyd;." `
    --add-binary "$tkDllDir\\tcl86t.dll;." `
    --add-binary "$tkDllDir\\tk86t.dll;." `
    --add-data "$tkPackageDir;tkinter" `
    --add-data "$tclRoot\\tcl8.6;_tcl_data" `
    --add-data "$tclRoot\\tk8.6;_tk_data" `
    $entryPoint

if (-not (Test-Path $distAppDir)) {
    throw "Build finished but could not find $distAppDir."
}

if (Test-Path $portableDir) {
    Remove-Item -LiteralPath $portableDir -Recurse -Force
}

if (Test-Path $portableZip) {
    Remove-Item -LiteralPath $portableZip -Force
}

New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
Copy-Item -LiteralPath $distAppDir -Destination $portableDir -Recurse
New-Item -ItemType Directory -Path $iconCacheDir -Force | Out-Null

Copy-Item -LiteralPath "README.md" -Destination $portableReadme -Force
Set-Content -LiteralPath $dataReadme -Value @(
    "This folder is created for the app's portable local data."
    ""
    "Darkest Dungeon Mod Manager stores its state, cache, and logs here beside the executable."
)
Set-Content -LiteralPath $iconKeep -Value ""

Compress-Archive -LiteralPath $portableDir -DestinationPath $portableZip -CompressionLevel Optimal

Write-Host ""
Write-Host "Build complete:"
Write-Host $distAppDir
Write-Host ""
Write-Host "Portable folder:"
Write-Host $portableDir
Write-Host ""
Write-Host "Portable zip:"
Write-Host $portableZip
