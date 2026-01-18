@echo off
echo Initializing Git repository...
git init

echo Adding files...
git add .

echo Committing files...
git commit -m "Fix: Switched provider to Pollinations.ai"

echo Renaming branch to main...
git branch -M main

echo Adding remote origin...
git remote remove origin 2>nul
git remote add origin https://github.com/Muqtada123mk/Bot-chatgpt-api.git

echo Pushing to GitHub (Forcing update)...
echo NOTE: You may be asked to sign in to GitHub in the popup window.
git push -u origin main --force

echo.
echo Upload complete!
pause
