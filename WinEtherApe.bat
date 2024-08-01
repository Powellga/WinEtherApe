@echo off
echo Step 1: Initialize Conda
& "C:\Users\gregg\Anaconda3\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo Failed to initialize Conda
    pause
    exit /b %errorlevel%
)

echo Step 2: Activate Conda Environment
conda activate winetherapeenv
if %errorlevel% neq 0 (
    echo Failed to activate Conda environment
    pause
    exit /b %errorlevel%
)

echo Step 3: Navigate to Project Directory
cd /d C:\Users\gregg\WinEtherApe
if %errorlevel% neq 0 (
    echo Failed to navigate to project directory
    pause
    exit /b %errorlevel%
)

echo Step 4: Run Python Script
python WinEtherApe.py
if %errorlevel% neq 0 (
    echo Failed to run Python script
    pause
    exit /b %errorlevel%
)

echo Step 5: Deactivate Conda Environment
conda deactivate
if %errorlevel% neq 0 (
    echo Failed to deactivate Conda environment
    pause
    exit /b %errorlevel%
)

echo Script completed successfully
pause