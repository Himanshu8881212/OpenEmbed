@echo off
REM ============================================================================
REM EMBEd - Easy Start Script for Windows
REM ============================================================================

echo.
echo ============================================
echo EMBEd - Multi-Modal Embedding Warehouse
echo ============================================
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed!
    echo Please install Docker Desktop from: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running!
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

echo [OK] Docker is installed and running
echo.

:menu
echo.
echo What would you like to do?
echo 1) Build and start EMBEd (first time setup)
echo 2) Start EMBEd
echo 3) Stop EMBEd
echo 4) Restart EMBEd
echo 5) View logs
echo 6) Check status
echo 7) Clean up (remove all data)
echo 8) Exit
echo.
set /p choice="Enter your choice [1-8]: "

if "%choice%"=="1" goto build_and_start
if "%choice%"=="2" goto start
if "%choice%"=="3" goto stop
if "%choice%"=="4" goto restart
if "%choice%"=="5" goto view_logs
if "%choice%"=="6" goto check_status
if "%choice%"=="7" goto clean_up
if "%choice%"=="8" goto exit
echo.
echo [ERROR] Invalid choice. Please enter 1-8.
goto menu

:build_and_start
echo.
echo Building Docker image (this may take 10-15 minutes on first run)...
docker-compose build
echo.
echo Starting EMBEd...
docker-compose up -d
echo.
echo Waiting for application to start...
timeout /t 5 /nobreak >nul
echo.
echo Checking logs...
docker-compose logs --tail=50
echo.
echo [OK] EMBEd is starting!
echo.
echo Access the application at:
echo   Frontend:    http://localhost:8000
echo   API Docs:    http://localhost:8000/docs
echo   Health:      http://localhost:8000/api/health
echo.
pause
goto menu

:start
echo.
echo Starting EMBEd...
docker-compose up -d
echo.
echo [OK] EMBEd started!
echo.
echo Access at: http://localhost:8000
echo.
pause
goto menu

:stop
echo.
echo Stopping EMBEd...
docker-compose down
echo.
echo [OK] EMBEd stopped!
echo.
pause
goto menu

:restart
echo.
echo Restarting EMBEd...
docker-compose restart
echo.
echo [OK] EMBEd restarted!
echo.
pause
goto menu

:view_logs
echo.
echo Viewing logs (press Ctrl+C to exit)...
echo.
docker-compose logs -f
goto menu

:check_status
echo.
echo Checking status...
echo.
docker-compose ps
echo.
echo Resource usage:
docker stats --no-stream embed-app 2>nul
echo.
echo Disk usage:
docker system df
echo.
pause
goto menu

:clean_up
echo.
echo [WARNING] This will delete ALL data including:
echo   - Vector database
echo   - Uploaded files
echo   - Analytics database
echo   - Model cache
echo.
set /p confirm="Are you sure? (yes/no): "
if /i "%confirm%"=="yes" (
    echo.
    echo Cleaning up...
    docker-compose down -v
    echo.
    echo [OK] All data removed!
) else (
    echo.
    echo [CANCELLED]
)
echo.
pause
goto menu

:exit
echo.
echo Goodbye!
exit /b 0

