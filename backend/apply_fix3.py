import sys
sys.path.insert(0, r'D:\researches\e2etest\backend')

with open(r'D:\researches\e2etest\backend\app\services\executor\test_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# The exact pattern to find (from line 892)
# It has log_step_end with 'skipped' followed by else:
old_pattern = """                            code_lines.append(f"                    log_step_end({i}, 'skipped')")
                        else:"""

# Replace with the fixed version - add except block after log_step_end
new_pattern = """                            code_lines.append(f"                    log_step_end({i}, 'skipped')")
                    except Exception as e:
                        code_lines.append(f"                    log_step_end({i}, 'failed', error_message=str(e))")
                        code_lines.append(f"                    raise")
                        else:"""

if old_pattern in content:
    content = content.replace(old_pattern, new_pattern)
    with open(r'D:\researches\e2etest\backend\app\services\executor\test_executor.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed!")
else:
    print("Pattern not found")
    # Debug: print the area around log_step_end
    idx = content.find("log_step_end({i}, 'skipped')")
    if idx >= 0:
        print("Found at:", idx)
        print(repr(content[idx-50:idx+100]))
