@echo off
echo Building YOLOv8 Trainer executable...

REM Install requirements
pip install -r requirements.txt
pip install pyinstaller

REM Build the executable
pyinstaller --name="YOLOv8_Trainer" --onefile --windowed --icon=icon.png --add-data="icon.png;." main.py

echo Build complete! Executable is in the dist folder.
echo You can now manually upload dist\YOLOv8_Trainer.exe to GitHub Releases.
pause
