[Setup]
AppId={{1DA0C8A3-D526-4BE0-9F49-A7F2A5B65CF9}
AppName=Paper Translator
AppVersion=2.0.0
DefaultDirName={localappdata}\Programs\PaperTranslator
DefaultGroupName=Paper Translator
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=PaperTranslator-Qt-Setup-2.0.0-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\PaperTranslator.exe
CloseApplications=yes
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Files]
Source: "..\dist\PaperTranslator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Paper Translator"; Filename: "{app}\PaperTranslator.exe"
Name: "{autodesktop}\Paper Translator"; Filename: "{app}\PaperTranslator.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\PaperTranslator.exe"; Description: "Launch Paper Translator"; Flags: nowait postinstall skipifsilent
