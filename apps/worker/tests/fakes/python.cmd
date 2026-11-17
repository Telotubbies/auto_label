@echo off
rem T-1019: a fake python for installer tests; it records each argv and runs nothing.
if not defined FAKE_LOG (
  echo FAKE_LOG is not set 1>&2
  exit /b 2
)
setlocal EnableDelayedExpansion
set "line=python"
:args
if "%~1"=="" goto record
set "line=!line!	%~1"
shift
goto args
:record
>>"%FAKE_LOG%" echo(!line!
echo python: fake, nothing installed
exit /b %FAKE_EXIT%
