@echo off
REM Script to set up a new GitHub repository for this project
REM Usage: setup_github_repo.bat <your-github-username> <repo-name>

if "%1"=="" (
    echo Usage: setup_github_repo.bat ^<your-github-username^> ^<repo-name^>
    echo Example: setup_github_repo.bat myusername lean-dojo-windows
    exit /b 1
)

if "%2"=="" (
    echo Usage: setup_github_repo.bat ^<your-github-username^> ^<repo-name^>
    echo Example: setup_github_repo.bat myusername lean-dojo-windows
    exit /b 1
)

set GITHUB_USER=%1
set REPO_NAME=%2

echo.
echo ========================================
echo Setting up GitHub repository
echo ========================================
echo.
echo GitHub Username: %GITHUB_USER%
echo Repository Name: %REPO_NAME%
echo.
echo Step 1: Creating initial commit...
git commit -m "Initial commit: Windows compatibility fixes for LeanDojo"

echo.
echo Step 2: Adding remote repository...
git remote add origin https://github.com/%GITHUB_USER%/%REPO_NAME%.git

echo.
echo ========================================
echo Next steps:
echo ========================================
echo.
echo 1. Create the repository on GitHub:
echo    - Go to https://github.com/new
echo    - Repository name: %REPO_NAME%
echo    - Choose public or private
echo    - DO NOT initialize with README, .gitignore, or license
echo    - Click "Create repository"
echo.
echo 2. Push to GitHub:
echo    git push -u origin main
echo.
echo ========================================

