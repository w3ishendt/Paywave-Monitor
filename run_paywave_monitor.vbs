Option Explicit

Dim shell
Dim fileSystem
Dim scriptDirectory
Dim pythonPath
Dim mainPath
Dim logsDirectory
Dim logPath
Dim argumentsText
Dim index
Dim launchCommand
Dim quote

Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

scriptDirectory = fileSystem.GetParentFolderName(WScript.ScriptFullName)
pythonPath = fileSystem.BuildPath(scriptDirectory, "venv\Scripts\python.exe")

If Not fileSystem.FileExists(pythonPath) Then
    pythonPath = fileSystem.BuildPath(scriptDirectory, "venv\Scripts\pythonw.exe")
End If

mainPath = fileSystem.BuildPath(scriptDirectory, "main.py")
logsDirectory = fileSystem.BuildPath(scriptDirectory, "logs")
logPath = fileSystem.BuildPath(logsDirectory, "paywave-monitor.log")

If Not fileSystem.FolderExists(logsDirectory) Then
    fileSystem.CreateFolder(logsDirectory)
End If

argumentsText = ""
For index = 0 To WScript.Arguments.Count - 1
    argumentsText = argumentsText & " " & Chr(34) & WScript.Arguments(index) & Chr(34)
Next

quote = Chr(34)
shell.CurrentDirectory = scriptDirectory
launchCommand = "cmd.exe /c " & quote & quote & pythonPath & quote & " " & quote & mainPath & quote & argumentsText & " >> " & quote & logPath & quote & " 2>&1" & quote

' Window style 0 hides the command window from the user.
shell.Run launchCommand, 0, False