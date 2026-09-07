Option Explicit

Dim shell
Dim fileSystem
Dim scriptDirectory
Dim pythonPath
Dim runnerPath
Dim commandText
Dim quote

Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

scriptDirectory = fileSystem.GetParentFolderName(WScript.ScriptFullName)
pythonPath = fileSystem.BuildPath(scriptDirectory, "venv\Scripts\python.exe")

If Not fileSystem.FileExists(pythonPath) Then
    pythonPath = "python"
End If

runnerPath = fileSystem.BuildPath(scriptDirectory, "icps_startup_runner.py")
quote = Chr(34)

commandText = "cmd.exe /c " & quote & quote & pythonPath & quote & " " & quote & runnerPath & quote & quote
shell.CurrentDirectory = scriptDirectory
shell.Run commandText, 0, False