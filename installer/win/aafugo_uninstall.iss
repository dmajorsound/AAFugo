; AAFUGO uninstaller for Windows (Inno Setup 6): removes the extension, keeps projects and audio
[Setup]
AppId=AAFUGO_Uninstaller
AppName=AAFUGO Uninstaller
AppVersion=0.1.0
AppPublisher=dmajorsound
AppPublisherURL=https://dmajorsound.com
DefaultDirName={userappdata}\REAPER\UserPlugins
DisableDirPage=no
DirExistsWarning=no
DisableProgramGroupPage=yes
DisableReadyPage=no
PrivilegesRequired=lowest
OutputBaseFilename=AAFUGO-0.1.0-win64-uninstall
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Uninstallable=no
CloseApplications=no
WizardStyle=modern
WizardImageFile=wizard-100.bmp,wizard-200.bmp
WizardSmallImageFile=small-100.bmp,small-200.bmp
WizardImageStretch=no
DisableWelcomePage=no

[Messages]
SetupWindowTitle=Uninstall AAFUGO
WelcomeLabel1=Uninstall AAFUGO
WelcomeLabel2=This removes the AAFUGO extension from REAPER.%n%nYour REAPER projects and imported audio stay untouched.%n%nPlease quit REAPER before you continue.
SelectDirLabel3=AAFUGO is removed from this REAPER UserPlugins folder. Change it only if you use a portable REAPER install.
SelectDirBrowseLabel=To continue, click Next.
WizardReady=Ready to uninstall
ReadyLabel1=AAFUGO will now be removed.
ReadyLabel2a=Click Uninstall to continue.
ButtonInstall=&Uninstall
WizardInstalling=Uninstalling
InstallingLabel=Please wait while AAFUGO is removed.
FinishedHeadingLabel=AAFUGO is removed
FinishedLabelNoIcons=AAFUGO has been removed from REAPER. Restart REAPER if it was open.
FinishedLabel=AAFUGO has been removed from REAPER. Restart REAPER if it was open.

[Files]
Source: "welcome-icon-100.bmp"; DestDir: "{tmp}"; Flags: dontcopy
Source: "welcome-icon-200.bmp"; DestDir: "{tmp}"; Flags: dontcopy
Source: "welcome-brand-100.bmp"; DestDir: "{tmp}"; Flags: dontcopy
Source: "welcome-brand-200.bmp"; DestDir: "{tmp}"; Flags: dontcopy

[Code]
#include "branding.iss"
procedure CurStepChanged(CurStep: TSetupStep);
var
  Unins, Dll: String;
  Code: Integer;
begin
  if CurStep <> ssInstall then exit;
  { the uninstaller the AAFUGO installer left behind also clears the Installed apps entry }
  Unins := ExpandConstant('{userappdata}\dmajorsound\AAFUGO\unins000.exe');
  if FileExists(Unins) then
    Exec(Unins, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Dll := AddBackslash(WizardDirValue) + 'reaper_aafugo.dll';
  if FileExists(Dll) and not DeleteFile(Dll) then
    MsgBox('AAFUGO could not be removed because REAPER is still running.' + #13#10 +
           'Quit REAPER and run this uninstaller again.', mbError, MB_OK);
  RegDeleteKeyIncludingSubkeys(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\AAFUGO_is1');
  DelTree(ExpandConstant('{userappdata}\dmajorsound\AAFUGO'), True, True, True);
end;

procedure InitializeWizard();
begin
  BrandWelcome('Uninstall AAFUGO',
    'This removes the AAFUGO extension from REAPER.' + #13#10 + #13#10 +
    'Quit REAPER first. Your projects stay untouched.');
end;
