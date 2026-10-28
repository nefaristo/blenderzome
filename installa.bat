@echo off
setlocal
echo.
echo Zome 2.0.5
echo Serve Blender 5.2.
echo.

set "QUI=%~dp0"
set "SORGENTE=%QUI%sistema\zome_loader.py"
set "DEST=%APPDATA%\Blender Foundation\Blender\5.2\scripts\addons"

if not exist "%SORGENTE%" (
  echo Estrai lo ZIP per intero in una cartella nuova, poi fai di nuovo doppio clic su questo file.
  pause
  exit /b 1
)
if not exist "%DEST%" mkdir "%DEST%"
copy /Y "%SORGENTE%" "%DEST%\zome_loader.py" >nul
if errorlevel 1 (
  echo Installazione non riuscita.
  pause
  exit /b 1
)
echo Fatto.
echo.
echo Apri Blender 5.2.
echo Preferenze, Add-ons, accendi Zome ^(pannello^).
echo Poi apri:
echo %QUI%Istanze\Sandbox\Sandbox.blend
echo.
echo Le prossime versioni le segnala il pannello. C'e' il tasto Aggiorna.
echo.
pause
