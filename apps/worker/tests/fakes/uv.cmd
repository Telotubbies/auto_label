@echo off
rem T-1019: a fake uv for installer tests; it records each argv and installs nothing.
if not defined FAKE_LOG (
  echo FAKE_LOG is not set 1>&2
  exit /b 2
)
setlocal EnableDelayedExpansion
set "line=uv"
:args
if "%~1"=="" goto record
set "line=!line!	%~1"
shift
goto args
:record
>>"%FAKE_LOG%" echo(!line!
echo uv: fake, nothing installed
exit /b %FAKE_EXIT%
