import re
with open('agent/tools/os_tools.py', 'r') as f:
    code = f.read()

# Make methods async
code = code.replace('def launch_app(', 'async def launch_app(')

# Add import and init
code = code.replace('from agent.security.permissions import PermissionManager', 'from agent.security.permissions import PermissionManager\nfrom agent.security.sandbox import SecureCommandRunner')

code = code.replace('self.permissions = PermissionManager()', 'self.permissions = PermissionManager()\n        self.command_runner = SecureCommandRunner()')

# Replace Popen
code = re.sub(r'subprocess\.Popen\(\s*\[?\s*target\s*,\s*raw_arg\s*\]?\s*\)', r'await self.command_runner.run(f"{target} {raw_arg}")', code)
code = re.sub(r'subprocess\.Popen\(cmd(?:,\s*shell=True)?\)', r'await self.command_runner.run(cmd)', code)

with open('agent/tools/os_tools.py', 'w') as f:
    f.write(code)

with open('agent/core/command_router.py', 'r') as f:
    cr = f.read()
cr = re.sub(r'self\.os_tools\.launch_app\(', r'await self.os_tools.launch_app(', cr)
with open('agent/core/command_router.py', 'w') as f:
    f.write(cr)
