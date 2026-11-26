; AAFUGO installer for Windows (Inno Setup 6)
[Setup]
AppName=AAFUGO
AppVersion=0.1.0
AppPublisher=dmajorsound
AppPublisherURL=https://dmajorsound.com
DefaultDirName={userappdata}\REAPER\UserPlugins
DisableDirPage=no
DirExistsWarning=no
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=AAFUGO-0.1.0-win64
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Uninstallable=yes
UninstallFilesDir={userappdata}\dmajorsound\AAFUGO
UninstallDisplayIcon={uninstallexe}
CloseApplications=no
UninstallDisplayName=AAFUGO (REAPER extension)
LicenseFile=..\..\LICENSE
WizardStyle=modern
WizardImageFile=wizard-100.bmp,wizard-200.bmp
WizardSmallImageFile=small-100.bmp,small-200.bmp
WizardImageStretch=no
DisableWelcomePage=no

[Files]
Source: "welcome-icon-100.bmp"; DestDir: "{tmp}"; Flags: dontcopy
Source: "welcome-icon-200.bmp"; DestDir: "{tmp}"; Flags: dontcopy
Source: "welcome-brand-100.bmp"; DestDir: "{tmp}"; Flags: dontcopy
Source: "welcome-brand-200.bmp"; DestDir: "{tmp}"; Flags: dontcopy
Source: "..\..\build\src\ext\Release\reaper_aafugo.dll"; DestDir: "{app}"; Flags: ignoreversion

[Messages]
SelectDirLabel3=AAFUGO goes into the REAPER UserPlugins folder. Change it only if you use a portable REAPER install.

[Code]
#include "branding.iss"

procedure InitializeWizard();
begin
  BrandWelcome('AAFUGO - Session Export for Reaper',
    'This installs the AAFUGO extension into the REAPER UserPlugins folder.' + #13#10 + #13#10 +
    'Quit REAPER first. Afterwards, start REAPER and open Extensions > AAFUGO.');
end;
