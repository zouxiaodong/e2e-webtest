import sys
sys.path.insert(0, r'D:\researches\e2etest\backend')

with open(r'D:\researches\e2etest\backend\app\services\executor\test_executor.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix lines 893-895 - wrong indentation
# Current:
# 893: except at 8 spaces
# 894: log_step_end at 4 spaces  
# 895: raise at 4 spaces
# Should be:
# 893: except at 24 spaces (same as try)
# 894: log_step_end at 24 spaces
# 895: raise at 24 spaces

lines[892] = "                        except Exception as e:\n"
lines[893] = '                            code_lines.append(f"                    log_step_end({i}, \'failed\', error_message=str(e))")\n'
lines[894] = "                            code_lines.append(f\"                    raise\")\n"

with open(r'D:\researches\e2etest\backend\app\services\executor\test_executor.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed!")
