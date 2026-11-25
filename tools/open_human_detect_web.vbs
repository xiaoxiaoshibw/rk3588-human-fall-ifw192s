' open_human_detect_web.vbs
' Desktop shortcut target: make sure the local static server for the
' human-detect page is up (start it hidden if not), then open the page
' in the default browser.
' The page itself is pure static; detection runs in the browser, the
' server only ships the files. Starting a second server on a busy port
' exits at once, harmless.

Option Explicit

Dim sh, py, root, port, page, cmd
Set sh = CreateObject("WScript.Shell")

py = "C:\Users\30680\AppData\Local\Programs\Python\Python314\python.exe"
root = "D:\Code\ldiar\_human_detect_20261116"
port = "8091"
page = "http://127.0.0.1:" & port & "/auto_leveling.html"

cmd = Chr(34) & py & Chr(34) & " -m http.server " & port & _
      " --bind 127.0.0.1 --directory " & Chr(34) & root & Chr(34)
sh.Run cmd, 0, False
WScript.Sleep 1800
sh.Run page, 1, False
