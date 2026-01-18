@echo off
echo Uploading to GitHub (No Reset)...

echo Adding changes...
git add .

echo Committing...
git commit -m "Update: Latest Bot API features (ChatGPT 5, Translate, YouTube)"

echo Ensuring main branch...
git branch -M main

echo Updating remote origin to https://github.com/cv1awaw/Test...
:: Try to remove it first in case it points somewhere else
git remote remove origin 2>nul
git remote add origin https://github.com/cv1awaw/Test

echo Pushing to GitHub...
git push -u origin main

echo ==============================================
echo Upload Complete (if no errors above).
echo ==============================================
pause
