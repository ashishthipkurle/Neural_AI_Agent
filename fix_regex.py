"""Fix: Remove duplicate line 172 and fix the bare JSON regex."""
import pathlib

f = pathlib.Path("agent/graph/nodes/coder.py")
lines = f.read_text(encoding="utf-8").split("\n")

# Find and fix the corrupt section around lines 170-183
new_lines = []
skip_until_return = False
i = 0
while i < len(lines):
    line = lines[i]
    
    # Detect the orphaned "for block in re.findall" that was injected by the previous fix
    if "for block in re.findall" in line and i+1 < len(lines) and "if not calls:" in lines[i+1]:
        # Skip this orphan line, then rewrite the whole Pattern 3 block
        i += 1  # skip orphan
        # Now we're at "if not calls:", skip that and its for+body
        new_lines.append("    ")
        new_lines.append("    # Pattern 3: Bare JSON with nested args")
        new_lines.append("    if not calls:")
        new_lines.append("        for block in re.findall(r'(\\{.*?\"name\"\\s*:\\s*\"[^\"]+\".*?\\})', text, re.DOTALL):")
        new_lines.append("            try:")
        new_lines.append("                parsed = json.loads(block)")
        new_lines.append('                if "name" in parsed:')
        new_lines.append('                    args = parsed.get("arguments", parsed.get("args", parsed.get("parameters", {})))')
        new_lines.append("                    if isinstance(args, str):")
        new_lines.append("                        try: args = json.loads(args)")
        new_lines.append("                        except: args = {}")
        new_lines.append("                    calls.append({\"name\": parsed[\"name\"], \"args\": args, \"id\": parsed.get(\"id\", f\"parsed_{parsed['name']}\")})")
        new_lines.append("            except: pass")
        # Skip the old Pattern 3 block (if not calls: + for + body)
        i += 1  # skip "if not calls:"  
        while i < len(lines) and not (lines[i].strip() == "" and i+1 < len(lines) and lines[i+1].strip().startswith("return")):
            i += 1
        continue
    
    new_lines.append(line)
    i += 1

f.write_text("\n".join(new_lines), encoding="utf-8")
print(f"Fixed. Total lines: {len(new_lines)}")
