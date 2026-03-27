"""Robust JSON object parser that avoids regex trap."""
import pathlib

f = pathlib.Path("agent/graph/nodes/coder.py")
content = f.read_text(encoding="utf-8")

old_block = """    # Pattern 3: Bare JSON with nested args
    if not calls:
        for block in re.findall(r'(\\{[^}]*"name"\\s*:\\s*"[^"]+".*?\\})', text, re.DOTALL):
            try:
                parsed = json.loads(block)
                if "name" in parsed:
                    args = parsed.get("arguments", parsed.get("args", parsed.get("parameters", {})))
                    if isinstance(args, str):
                        try: args = json.loads(args)
                        except: args = {}
                    calls.append({"name": parsed["name"], "args": args, "id": parsed.get("id", f"parsed_{parsed['name']}")})
            except: pass"""

old_block_alt = """    # Pattern 3: Bare JSON objects with "name" key (greedy but effective)
    if not calls:
        for block in re.findall(r'(\\{[^{}]*"name"\\s*:\\s*"[^"]+"[^{}]*\\})', text, re.DOTALL):
            try:
                parsed = json.loads(block)
                if "name" in parsed:
                    args = parsed.get("arguments", parsed.get("args", parsed.get("parameters", {})))
                    if isinstance(args, str):
                        try: args = json.loads(args)
                        except: args = {}
                    calls.append({"name": parsed["name"], "args": args, "id": parsed.get("id", f"parsed_{parsed['name']}")})
            except: pass"""

new_block = """    # Pattern 3: Brute-force extract balanced JSON objects containing "name"
    if not calls:
        idx = 0
        while idx < len(text):
            start = text.find('{', idx)
            if start == -1:
                break
            
            # Find matching closing brace
            braces = 0
            end = -1
            in_string = False
            escape = False
            
            for i in range(start, len(text)):
                char = text[i]
                if escape:
                    escape = False
                    continue
                if char == '\\\\':
                    escape = True
                    continue
                if char == '"':
                    in_string = not in_string
                    continue
                    
                if not in_string:
                    if char == '{':
                        braces += 1
                    elif char == '}':
                        braces -= 1
                        if braces == 0:
                            end = i + 1
                            break
                            
            if end != -1:
                block = text[start:end]
                try:
                    parsed = json.loads(block)
                    if isinstance(parsed, dict) and "name" in parsed:
                        args = parsed.get("arguments", parsed.get("args", parsed.get("parameters", {})))
                        if isinstance(args, str):
                            try: args = json.loads(args)
                            except: args = {}
                        calls.append({"name": parsed["name"], "args": args, "id": parsed.get("id", f"parsed_{parsed['name']}")})
                except:
                    pass
                idx = start + 1  # check next position even if we found one
            else:
                idx = start + 1
"""

if old_block in content:
    content = content.replace(old_block, new_block)
    f.write_text(content, encoding="utf-8")
    print("Replaced old_block correctly")
elif old_block_alt in content:
    content = content.replace(old_block_alt, new_block)
    f.write_text(content, encoding="utf-8")
    print("Replaced old_block_alt correctly")
else:
    print("Could not find Pattern 3 block in file!")
    # Let's string inject if we can
    lines = content.split('\\n')
    for i, l in enumerate(lines):
        if "# Pattern 3" in l and "Bare JSON" in l:
            print(f"Found Pattern 3 at line {i+1}")
            start_i = i
            end_i = i
            while end_i < len(lines) and not ("return calls" in lines[end_i]):
                end_i += 1
            if end_i < len(lines):
                new_lines = lines[:start_i] + new_block.split('\\n') + lines[end_i:]
                f.write_text("\\n".join(new_lines), encoding="utf-8")
                print("Replaced dynamically")
            break
"""
