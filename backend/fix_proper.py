import sys
sys.path.insert(0, r'D:\researches\e2etest\backend')

with open(r'D:\researches\e2etest\backend\app\services\executor\test_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# The original broken section has:
# Line 892: log_step_end({i}, 'skipped') at 24 spaces
# Line 893: else: at 16 spaces (WRONG - this is at if level, not try level)
#
# We need to:
# 1. Add except block after log_step_end (at 24 spaces)
# 2. Remove the incorrect else:

old_text = """                            code_lines.append(f"                    log_step_end({i}, 'skipped')")
                        else:"""

new_text = """                            code_lines.append(f"                    log_step_end({i}, 'skipped')")
                            except Exception as e:
                                code_lines.append(f"                    log_step_end({i}, 'failed', error_message=str(e))")
                                code_lines.append(f"                    raise")"""

if old_text in content:
    content = content.replace(old_text, new_text)
    with open(r'D:\researches\e2etest\backend\app\services\executor\test_executor.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: Fix applied with correct indentation!")
else:
    print("ERROR: Pattern not found")
