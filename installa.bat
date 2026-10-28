@echo off
setlocal
echo.
echo Zome 2.0.1
echo Serve Blender 5.2 su Windows.
echo.
echo Copia solo il pannello negli add-on di Blender 5.2.
echo Non installa Python. Non apre e non sovrascrive nessun blend.
echo Gli aggiornamenti, dopo questo, si fanno dal pannello dentro Blender.
echo.

set "QUI=%~dp0"
set "SORGENTE=%QUI%sistema\zome_loader.py"
set "DEST=%APPDATA%\Blender Foundation\Blender\5.2\scripts\addons"

if not exist "%SORGENTE%" (
  echo Non trovo sistema\zome_loader.py.
  echo Estrai lo ZIP per intero, poi fai doppio clic su questo file da quella cartella.
  pause
  exit /b 1
)
if not exist "%DEST%" mkdir "%DEST%"
copy /Y "%SORGENTE%" "%DEST%\zome_loader.py" >nul
if errorlevel 1 (
  echo Copia non riuscita.
  pause
  exit /b 1
)
echo Pannello copiato.
echo Versione riportata: Zome 2.0.1, Blender 5.2.
echo.
echo Adesso apri Blender 5.2.
echo Preferenze, Add-ons, accendi Zome ^(pannello^).
echo Poi apri:
echo %QUI%Istanze\Sandbox\Sandbox.blend
echo.
pause
