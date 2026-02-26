import sys
sys.path.insert(0, r'D:\researches\e2etest\backend')

with open(r'D:\researches\e2etest\backend\app\services\executor\test_executor.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and fix line 892 (index 891) - add except block after it
new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    if i == 891:  # After line 892
        # Add except block at same indentation as try (24 spaces)
        new_lines.append("                        except Exception as e:\n")
        new_lines.append('                            code_lines.append(f"                    log_step_end({i}, \'failed\', error_message=str(e))")\n')
        new_lines.append("                            code_lines.append(f\"                    raise\")\n")

with open(r'D:\researches\e2etest\backend\app\services\executor\test_executor.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Fixed!")
