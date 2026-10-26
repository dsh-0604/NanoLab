# 把一段文字发进豆包（当前打开的对话）
# 用法：powershell -NoProfile -ExecutionPolicy Bypass -File tools\say_to_doubao.ps1 -File "C:\path\msg.md"
param(
  [Parameter(Mandatory = $true)][string]$File
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System; using System.Runtime.InteropServices; using System.Text;
public class DoubaoWin {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
}
"@

$p = Get-Process Doubao -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle } | Select-Object -First 1
if (-not $p) { Write-Output "NO_DOUBAO"; exit 1 }
$h = $p.MainWindowHandle
[DoubaoWin]::ShowWindow($h, 9) | Out-Null
[DoubaoWin]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 800
if ([DoubaoWin]::GetForegroundWindow() -ne $h) {
  $ws = New-Object -ComObject WScript.Shell
  $ws.AppActivate($p.Id) | Out-Null
  Start-Sleep -Milliseconds 800
}
if ([DoubaoWin]::GetForegroundWindow() -ne $h) { Write-Output "NO_FOREGROUND"; exit 1 }

Set-Clipboard -Value (Get-Content $File -Raw -Encoding UTF8)
$win = [System.Windows.Automation.AutomationElement]::FromHandle($h)
$all = $win.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
$editor = $null
foreach ($e in $all) {
  if ($e.Current.ClassName -match 'tiptap' -and $e.Current.ClassName -match 'ProseMirror') { $editor = $e; break }
}
if (-not $editor) { Write-Output "NO_EDITOR"; exit 1 }
$editor.SetFocus()
Start-Sleep -Milliseconds 400
[System.Windows.Forms.SendKeys]::SendWait("^v")
Start-Sleep -Seconds 2
$len = 0
try {
  $tp = $editor.GetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern)
  $len = $tp.DocumentRange.GetText(-1).Length
} catch { }
if ($len -lt 30) { Write-Output "PASTE_FAILED"; exit 1 }
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
Start-Sleep -Seconds 2
Write-Output ("SENT chars=" + $len)
