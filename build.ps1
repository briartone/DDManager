$ErrorActionPreference = "Stop"

$appName = "DD Manager"
$entryPoint = "dd2.py"
$pythonRoot = python -c "import sys; print(sys.base_prefix)"
$tkDllDir = Join-Path $pythonRoot "DLLs"
$tclRoot = Join-Path $pythonRoot "tcl"
$tkPackageDir = Join-Path $pythonRoot "Lib\\tkinter"
$runtimeHook = "pyi_rth_tk_paths.py"

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

Write-Host ""
Write-Host "Build complete:"
Write-Host "dist\\$appName\\$appName.exe"
