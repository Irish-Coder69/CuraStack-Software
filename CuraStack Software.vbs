Option Explicit
' DEVELOPER LAUNCH SCRIPT - Requires Python (venv) on this machine.
' End users should run the installed CuraStack Software.exe created by build_installer.ps1.

Dim shell, fso, scriptDir, mainPy, venvPythonw, cmd

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
mainPy = fso.BuildPath(scriptDir, "main.py")
venvPythonw = fso.BuildPath(fso.BuildPath(scriptDir, ".venv\Scripts"), "pythonw.exe")

If Not fso.FileExists(mainPy) Then
    MsgBox "main.py was not found in this folder.", vbCritical, "CuraStack Software"
    WScript.Quit 1
End If

If fso.FileExists(venvPythonw) Then
    cmd = Chr(34) & venvPythonw & Chr(34) & " " & Chr(34) & mainPy & Chr(34)
Else
    cmd = "cmd /c pyw -3 " & Chr(34) & mainPy & Chr(34)
End If

shell.CurrentDirectory = scriptDir
shell.Run cmd, 0, False