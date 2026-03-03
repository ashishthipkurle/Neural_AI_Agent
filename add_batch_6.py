import re

file_path = r'd:\All Projects\My AI Agent\agent\core\pc_commands.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

additions = {
    'SYSTEM_POWER_COMMANDS': '''
    "power down immediate":      {"action": "terminal", "params": {"command": "shutdown /s /f /t 0"}},
    "reboot immediate":          {"action": "terminal", "params": {"command": "shutdown /r /f /t 0"}},
    "abort pending shutdown":    {"action": "terminal", "params": {"command": "shutdown /a"}},
    "hibernate system now":      {"action": "terminal", "params": {"command": "shutdown /h"}},
    "logoff session now":        {"action": "terminal", "params": {"command": "shutdown /l"}},
    "advanced startup options":  {"action": "terminal", "params": {"command": "shutdown /r /o /t 0"}},
    "set power scheme high":     {"action": "terminal", "params": {"command": "powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"}},
    "set power scheme balanced": {"action": "terminal", "params": {"command": "powercfg /setactive 381b4222-f694-41f0-9685-ff5bb260df2e"}},
    "set power scheme saver":    {"action": "terminal", "params": {"command": "powercfg /setactive a1841308-3541-4fab-bc81-f71556f20b4a"}},
    "generate battery report":   {"action": "terminal", "params": {"command": "powercfg /batteryreport"}},
    "generate sleep study":      {"action": "terminal", "params": {"command": "powercfg /sleepstudy"}},
    "generate energy report":    {"action": "terminal", "params": {"command": "powercfg /energy"}},
    "enable fast startup":       {"action": "terminal", "params": {"command": "powercfg /h on"}},
    "disable fast startup":      {"action": "terminal", "params": {"command": "powercfg /h off"}},
    "list power schemes":        {"action": "terminal", "params": {"command": "powercfg /list"}},
    "query active power scheme": {"action": "terminal", "params": {"command": "powercfg /getactivescheme"}},
    "wake timers query":         {"action": "terminal", "params": {"command": "powercfg /waketimers"}},
    "device query wake armed":   {"action": "terminal", "params": {"command": "powercfg /devicequery wake_armed"}},
    "last wake query":           {"action": "terminal", "params": {"command": "powercfg /lastwake"}},
    "system power requests":     {"action": "terminal", "params": {"command": "powercfg /requests"}},
    "lock workstation screen":   {"action": "terminal", "params": {"command": "rundll32.exe user32.dll,LockWorkStation"}},
    "turn display off now":      {"action": "terminal", "params": {"command": "powershell (Add-Type '[DllImport(\\\"user32.dll\\\")]^public static extern int SendMessage(int hWnd, int hMsg, int wParam, int lParam);' -Name a -PassThru)::SendMessage(-1,0x0112,0xF170,2)"}},
    "schedule reboot tonight":   {"action": "system", "params": {"operation": "schedule_reboot_tonight"}},
    "schedule shutdown tonight": {"action": "system", "params": {"operation": "schedule_shutdown_tonight"}},
    "cancel scheduled reboot":   {"action": "system", "params": {"operation": "cancel_reboot"}},
    "cancel scheduled shutdown": {"action": "system", "params": {"operation": "cancel_shutdown"}},
    "open power control panel":  {"action": "launch", "params": {"app_name": "powercfg.cpl"}},
    "open edit power plan":      {"action": "launch", "params": {"app_name": "control /name Microsoft.PowerOptions /page pagePlanSettings"}},
    "check system uptime":       {"action": "terminal", "params": {"command": "powershell (get-date) - (gcim Win32_OperatingSystem).LastBootUpTime"}},
    "open task manager advanced": {"action": "terminal", "params": {"command": "taskmgr /7"}},
'''
}

for dict_name, new_commands in additions.items():
    pattern = re.compile(rf"({dict_name}: Dict\[str, Dict\[str, Any\]\] = {{.*?)(\n}})", re.DOTALL)
    content = pattern.sub(rf"\g<1>{new_commands}\g<2>", content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Successfully added 30 commands to SYSTEM_POWER_COMMANDS!")
