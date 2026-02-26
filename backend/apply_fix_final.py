import sys
sys.path.insert(0, r'D:\researches\e2etest\backend')

with open(r'D:\researches\e2etest\backend\app\services\executor\test_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# The exact original line 892 from git
old = """                            code_lines.append(f"                    log_step_end({i}, 'skipped')")
                        else:"""

# Fix: add except block after log_step_end line
# Note: try is at 16 spaces inside generated code, so except should also be at 16 spaces
new = """                            code_lines.append(f"                    log_step_end({i}, 'skipped')")
                            code_lines.append(f"                except Exception as e:")
                            code_lines.append(f"                    log_step_end({i}, 'failed', error_message=str(e))")
                            code_lines.append(f"                    raise")
                        else:"""

if old in content:
    content = content.replace(old, new)
    with open(r'D:\researches\e2etest\backend\app\services\executor\test_executor.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed!")
else:
    print("Pattern not found")
