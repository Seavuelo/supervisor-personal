Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

If CreateObject("Scripting.FileSystemObject").FileExists(".venv\Scripts\pythonw.exe") Then
    WshShell.Run """.venv\Scripts\pythonw.exe"" run_seeu.py", 0, False
Else
    WshShell.Run "pythonw run_seeu.py", 0, False
End If
