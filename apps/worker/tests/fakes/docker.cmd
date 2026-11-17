@echo off
rem T-1019: a fake docker for installer tests; it records each argv and pulls nothing.
if not defined FAKE_LOG (
  echo FAKE_LOG is not set 1>&2
  exit /b 2
)
setlocal EnableDelayedExpansion
set "line=docker"
:args
if "%~1"=="" goto record
set "line=!line!	%~1"
shift
goto args
:record
>>"%FAKE_LOG%" echo(!line!
echo docker: fake, nothing installed
exit /b %FAKE_EXIT%
