[Setup]
AppName=USB Port Monitor
AppVersion=1.0
DefaultDirName={autopf}\USBGuard
OutputBaseFilename=USBGuard_Setup
SetupIconFile=D:\USB_Moniter_tool\hacker_new.ico
PrivilegesRequired=admin

[Files]
Source: "D:\USB_Moniter_tool\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion; Excludes: "__pycache__,*.pyc,venv,Output,.git,*.spec,build,dist"
Source: "C:\Users\AMAAN\AppData\Local\Python\pythoncore-3.15-64\*"; DestDir: "{app}\python"; Flags: recursesubdirs ignoreversion; Excludes: "__pycache__,*.pyc"

[Run]
Filename: "{app}\python\python.exe"; Parameters: "-m ensurepip --upgrade"; StatusMsg: "Pip setup ho raha hai..."; Flags: runhidden waituntilterminated
Filename: "{app}\python\python.exe"; Parameters: "-m pip install -r ""{app}\requirements.txt"""; StatusMsg: "Requirements install ho rahi hain..."; Flags: runhidden waituntilterminated

[Icons]
Name: "{autodesktop}\USB Port Monitor"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\USBGuard_App.py"""; WorkingDir: "{app}"; IconFilename: "{app}\hacker_new.ico"
Name: "{group}\USB Port Monitor"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\USBGuard_App.py"""; WorkingDir: "{app}"; IconFilename: "{app}\hacker_new.ico"