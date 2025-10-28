<#
Copyright 2025 H2so4 Consulting LLC
Build script for Deid Windows distribution.
This script:
  1. Activates the virtual environment
  2. Installs dependencies (if needed)
  3. Downloads spaCy model (if missing)
  4. Runs PyInstaller in onedir, windowed mode
  5. Writes logs to build_log.txt
#>

Write-Host "=== Building Deid ==="

# --- Configuration ---------------------------------------------------------
$venvPath = ".\venv"
$python = "$venvPath\Scripts\python.exe"
$pyInstallerArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onedir",
    "--windowed",
    "--name", "Deid",
    "app\main.py"
)
$logFile = "build_log.txt"
# ---------------------------------------------------------------------------

# --- Verify environment ----------------------------------------------------
if (-not (Test-Path $python)) {
    Write-Host "Virtual environment not found at $venvPath" -ForegroundColor Red
    Write-Host "Creating virtual environment..."
    python -m venv $venvPath
}

Write-Host "Activating venv and installing requirements..."
& $python -m pip install --upgrade pip > $logFile
& $python -m pip install pyinstaller pyside6 bcrypt spacy pdfminer.six python-docx openpyxl python-pptx -q >> $logFile

# --- Ensure spaCy model is present ----------------------------------------
Write-Host "Checking spaCy model..."
try {
    & $python -c "import en_core_web_sm" 2>$null
} catch {
    Write-Host "Downloading spaCy model..."
    & $python -m spacy download en_core_web_sm >> $logFile
}

# --- Run PyInstaller -------------------------------------------------------
Write-Host "Running PyInstaller..."
& $python @pyInstallerArgs | Tee-Object -FilePath $logFile

# --- Done -----------------------------------------------------------------
if (Test-Path ".\dist\Deid\Deid.exe") {
    Write-Host "`n✅ Build complete!"
    Write-Host "Output directory: dist\Deid"
    Write-Host "You can zip that folder and send it to users."
} else {
    Write-Host "`n❌ Build failed. See $logFile for details." -ForegroundColor Red
}

Pause
