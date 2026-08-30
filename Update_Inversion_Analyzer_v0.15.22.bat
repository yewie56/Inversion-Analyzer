@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem ============================================================
rem Inversion Analyzer v0.15.22 - safe GitHub uploader
rem ASCII file: no UTF-8 BOM.
rem
rem Put this BAT next to Inversion_Analyzer_v0.15.22.zip
rem and start it from Anaconda Prompt / PowerShell.
rem ============================================================

set "EXPECTED_VERSION=0.15.22"
set "EXPECTED_REMOTE=yewie56/Inversion-Analyzer"
set "ZIP=%~1"
if not defined ZIP set "ZIP=%~dp0Inversion_Analyzer_v0.15.22.zip"
set "REPO=%~2"
set "TMP=%TEMP%\InversionAnalyzer_v%EXPECTED_VERSION%_%RANDOM%_%RANDOM%"
set "COMMITMSG=Release v%EXPECTED_VERSION% - central KITMast reference archive"

echo.
echo ============================================================
echo Inversion Analyzer v%EXPECTED_VERSION% - GitHub Update
echo ============================================================
echo Release ZIP: %ZIP%
echo.

where git >nul 2>&1
if errorlevel 1 (
  set "ERRORMSG=Git not found in PATH."
  goto :fatal
)
where powershell >nul 2>&1
if errorlevel 1 (
  set "ERRORMSG=PowerShell not found."
  goto :fatal
)
where python >nul 2>&1
if errorlevel 1 (
  set "ERRORMSG=Python not found. Start from Anaconda Prompt or activate the environment."
  goto :fatal
)
if not exist "%ZIP%" (
  set "ERRORMSG=Release ZIP not found: %ZIP%"
  goto :fatal
)

if defined REPO goto :repo_check
call :tryrepo "%CD%"
if defined REPO goto :repo_check
call :tryrepo "%USERPROFILE%\AnacondaProjects\InversionsTrend"
if defined REPO goto :repo_check
call :tryrepo "%USERPROFILE%\AnacondaProjects\InversionsTrendTest"
if defined REPO goto :repo_check
for %%P in ("%~dp0..") do call :tryrepo "%%~fP"
if defined REPO goto :repo_check

echo.
echo No Git repository was found automatically.
set /p "REPO=Repository path: "
if not defined REPO (
  set "ERRORMSG=No repository path entered."
  goto :fatal
)

:repo_check
for %%R in ("%REPO%") do set "REPO=%%~fR"
git -C "%REPO%" rev-parse --show-toplevel >nul 2>&1
if errorlevel 1 (
  set "ERRORMSG=Selected directory is not a Git repository: %REPO%"
  goto :fatal
)
for /f "usebackq delims=" %%R in (`git -C "%REPO%" rev-parse --show-toplevel`) do set "REPO=%%R"

echo Repository : %REPO%

for /f "delims=" %%R in ('git -C "%REPO%" remote get-url origin 2^>nul') do set "REMOTE=%%R"
if not defined REMOTE (
  set "ERRORMSG=Git remote origin is missing."
  goto :fatal
)
echo Remote     : %REMOTE%
echo %REMOTE% | findstr /I /C:"%EXPECTED_REMOTE%" >nul
if errorlevel 1 (
  set "ERRORMSG=Wrong GitHub repository. Expected %EXPECTED_REMOTE%."
  goto :fatal
)

for /f "delims=" %%B in ('git -C "%REPO%" branch --show-current') do set "BRANCH=%%B"
if /I not "%BRANCH%"=="main" (
  set "ERRORMSG=Current branch is '%BRANCH%'. Expected main."
  goto :fatal
)

echo.
echo [0/10] Calculate release SHA256 ...
for /f "usebackq delims=" %%H in (`powershell -NoProfile -Command "(Get-FileHash -Algorithm SHA256 -LiteralPath '%ZIP%').Hash.ToLower()"`) do set "ACTUAL_SHA256=%%H"
if not defined ACTUAL_SHA256 (
  set "ERRORMSG=Could not calculate ZIP SHA256."
  goto :fatal
)
echo SHA256: %ACTUAL_SHA256%
echo Release version and required files will be verified after extraction.

echo.
echo [1/10] Check existing local changes ...
set "BAD_DIRTY="
for /f "usebackq delims=" %%L in (`git -C "%REPO%" status --porcelain --untracked-files=all`) do (
  set "LINE=%%L"
  set "PATHPART=!LINE:~3!"
  echo !PATHPART! | findstr /I /B /C:"archive/" /C:"logs/" /C:"cache/" >nul
  if errorlevel 1 (
    set "BAD_DIRTY=1"
    echo   Existing non-runtime change: !LINE!
  )
)
if defined BAD_DIRTY (
  echo Existing code/config changes were found.
  set "ERRORMSG=Repository is not clean enough for an automatic release update."
  goto :fatal
)

echo.
echo [2/10] Fetch and rebase from GitHub ...
git -C "%REPO%" fetch origin
if errorlevel 1 (
  set "ERRORMSG=git fetch origin failed."
  goto :fatal
)
git -C "%REPO%" pull --rebase --autostash origin main
if errorlevel 1 (
  echo Do NOT use force push.
  set "ERRORMSG=git pull --rebase --autostash failed."
  goto :fatal
)

echo.
echo [3/10] Extract release ZIP ...
if exist "%TMP%" rmdir /s /q "%TMP%"
mkdir "%TMP%"
if errorlevel 1 (
  set "ERRORMSG=Could not create temporary directory."
  goto :fatal
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%ZIP%' -DestinationPath '%TMP%' -Force"
if errorlevel 1 (
  set "ERRORMSG=Could not extract ZIP."
  goto :fatal
)

set "SRC="
for /d %%D in ("%TMP%\Inversion_Analyzer_v%EXPECTED_VERSION%*") do (
  if not defined SRC set "SRC=%%~fD"
)
if not defined SRC (
  set "ERRORMSG=Release root Inversion_Analyzer_v%EXPECTED_VERSION% was not found in ZIP."
  goto :fatal
)
if not exist "%SRC%\Inversion_Server.py" (
  set "ERRORMSG=Release incomplete: Inversion_Server.py missing."
  goto :fatal
)
if not exist "%SRC%\inversion\config.py" (
  set "ERRORMSG=Release incomplete: inversion\config.py missing."
  goto :fatal
)
findstr /C:"VERSION = \"%EXPECTED_VERSION%\"" "%SRC%\inversion\config.py" >nul
if errorlevel 1 (
  set "ERRORMSG=Release version check failed."
  goto :fatal
)

echo.
echo [4/10] Copy release files into repository ...
echo Runtime data and local config are preserved.
robocopy "%SRC%" "%REPO%" /E /R:2 /W:1 /NFL /NDL /NJH /NJS ^
  /XD archive logs cache __pycache__ .git ^
  /XF settings.json locations.json archive_config.json *.pyc *.pyo >nul
set "RC=%ERRORLEVEL%"
if %RC% GEQ 8 (
  set "ERRORMSG=Robocopy failed with code %RC%."
  goto :fatal
)

pushd "%REPO%"
if errorlevel 1 (
  set "ERRORMSG=Could not enter repository directory."
  goto :fatal
)

echo.
echo [5/10] Run regression tests and selftest ...
python test_kit_reference_archive_v0_15_22.py
if errorlevel 1 (
  set "TESTNAME=test_kit_reference_archive_v0_15_22.py"
  goto :test_failed
)
python test_workflow_global_kit_v0_15_22.py
if errorlevel 1 (
  set "TESTNAME=test_workflow_global_kit_v0_15_22.py"
  goto :test_failed
)
python test_workflow_dispatch_modes_v0_15_21.py
if errorlevel 1 (
  set "TESTNAME=test_workflow_dispatch_modes_v0_15_21.py"
  goto :test_failed
)
python test_kit_missing_level_v0_15_20.py
if errorlevel 1 (
  set "TESTNAME=test_kit_missing_level_v0_15_20.py"
  goto :test_failed
)
python test_kit_robustness_v0_15_19.py
if errorlevel 1 (
  set "TESTNAME=test_kit_robustness_v0_15_19.py"
  goto :test_failed
)
python test_kit_github_archive_v0_15_18.py
if errorlevel 1 (
  set "TESTNAME=test_kit_github_archive_v0_15_18.py"
  goto :test_failed
)
python Inversion_Server.py --selftest
if errorlevel 1 (
  set "TESTNAME=Inversion_Server.py --selftest"
  goto :test_failed
)

echo.
echo [6/10] Stage release changes ...
git add -A .
if errorlevel 1 (
  set "ERRORMSG=git add failed."
  goto :fatal_popd
)

git reset -q HEAD -- archive 2>nul
git reset -q HEAD -- logs 2>nul
git reset -q HEAD -- cache 2>nul
git reset -q HEAD -- settings.json 2>nul
git reset -q HEAD -- locations.json 2>nul
git reset -q HEAD -- archive_config.json 2>nul

set "BAD_STAGE="
for /f "delims=" %%F in ('git diff --cached --name-only') do (
  echo %%F | findstr /I /B /C:"archive/" /C:"logs/" /C:"cache/" >nul
  if not errorlevel 1 (
    set "BAD_STAGE=1"
    echo   Forbidden staged runtime file: %%F
  )
)
if defined BAD_STAGE (
  git reset
  set "ERRORMSG=Runtime data was staged. Staging has been reset."
  goto :fatal_popd
)

git diff --cached --quiet
if not errorlevel 1 (
  set "ERRORMSG=No release changes found. v%EXPECTED_VERSION% may already be installed."
  goto :fatal_popd
)

echo.
echo -------- STAGED FILES --------
git diff --cached --name-status
echo.
echo -------- DIFF STAT --------
git diff --cached --stat

echo.
echo [7/10] Final confirmation
choice /C JN /N /M "Commit and push these changes as v%EXPECTED_VERSION%? [J/N]: "
if errorlevel 2 (
  echo Cancelled. Nothing was committed or pushed.
  goto :success_popd
)

echo.
echo [8/10] Create commit ...
git commit -m "%COMMITMSG%"
if errorlevel 1 (
  set "ERRORMSG=git commit failed."
  goto :fatal_popd
)

echo.
echo [9/10] Synchronize once more before push ...
git pull --rebase --autostash origin main
if errorlevel 1 (
  echo Do NOT use force push.
  set "ERRORMSG=Final rebase before push failed."
  goto :fatal_popd
)

echo.
echo [10/10] Push to GitHub ...
git push origin main
if errorlevel 1 (
  echo No force push was attempted.
  set "ERRORMSG=git push origin main failed."
  goto :fatal_popd
)

echo.
echo ============================================================
echo SUCCESS: v%EXPECTED_VERSION% pushed to GitHub.
echo ============================================================
git log --oneline -3
echo.
echo Remaining local changes:
git status --short

where gh >nul 2>&1
if errorlevel 1 goto :success_popd

echo.
choice /C JN /N /M "Start a MANUAL SCHEDULED GitHub Actions test for ALL locations now? [J/N]: "
if errorlevel 2 goto :success_popd

gh auth status >nul 2>&1
if errorlevel 1 (
  echo GitHub CLI is not authenticated. Workflow was not started.
  goto :success_popd
)

gh workflow run inversion_collect.yml --ref main -f location=ALL -f mode=scheduled -f force=false -f date=
if errorlevel 1 (
  echo WARNING: Push succeeded, but workflow start failed.
  goto :success_popd
)

echo GitHub Actions scheduled-mode test started.
echo Use: gh run list --limit 5
echo Then: gh run watch RUN_ID

:success_popd
popd
if exist "%TMP%" rmdir /s /q "%TMP%"
echo.
pause
exit /b 0

:test_failed
echo.
echo ============================================================
echo TEST FAILED: %TESTNAME%
echo ============================================================
echo Nothing will be committed or pushed.
git status --short
popd
if exist "%TMP%" rmdir /s /q "%TMP%"
pause
exit /b 20

:fatal_popd
popd
goto :fatal

:fatal
echo.
echo ============================================================
echo ERROR
echo ============================================================
echo %ERRORMSG%
echo.
if exist "%TMP%" rmdir /s /q "%TMP%"
pause
exit /b 10

:tryrepo
set "CAND=%~1"
if not exist "%CAND%" exit /b 0
git -C "%CAND%" rev-parse --show-toplevel >nul 2>&1
if errorlevel 1 exit /b 0
for /f "usebackq delims=" %%R in (`git -C "%CAND%" rev-parse --show-toplevel`) do set "REPO=%%R"
exit /b 0
