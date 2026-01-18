@echo off
echo WARNING: This will delete your entire Git history and start fresh.
echo Press CTRL+C to cancel or any key to continue...
pause

echo Deleting existing .git directory...
if exist .git (
    rmdir /s /q .git
    echo .git directory deleted.
) else (
    echo No .git directory found.
)

echo Initializing new Git repository...
git init

echo Adding all files to staging...
git add .

echo Committing files...
git commit -m "Initial commit: Upgraded with ChatGPT 5, Translator, Youtube API, and Mind Map"

echo Renaming branch to main...
git branch -M main

echo Adding remote origin https://github.com/cv1awaw/Test...
git remote add origin https://github.com/cv1awaw/Test

echo Pushing to remote (Force)...
git push -u origin main --force

echo ==============================================
echo Git repository has been reset and initialized.
echo All current files are committed.
echo ==============================================
pause
