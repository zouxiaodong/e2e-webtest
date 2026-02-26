import sys
sys.path.insert(0, r'D:\researches\e2etest\backend')

# Read the original file from git
with open(r'D:\researches\e2etest\backend\app\services\executor\test_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the broken section
# Original:
#                             code_lines.append(f"                    log_step_end({i}, 'skipped')")
#                         else:
# 
# Fixed:
#                             code_lines.append(f"                    log_step_end({i}, 'skipped')")
#                         except Exception as e:
#                             code_lines.append(f"                    log_step_end({i}, 'failed', error_message=str(e))")
#                             code_lines.append(f"                    raise")
#                         else:

old_text = """                            code_lines.append(f"                    log_step_end({i}, 'skipped')")
                        else:"""

new_text = """                            code_lines.append(f"                    log_step_end({i}, 'skipped')")
                        except Exception as e:
                            code_lines.append(f"                    log_step_end({i}, 'failed', error_message=str(e))")
                            code_lines.append(f"                    raise")
                        else:"""

if old_text in content:
    content = content.replace(old_text, new_text)
    with open(r'D:\researches\e2etest\backend\app\services\executor\test_executor.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: Fix applied!")
else:
    print("ERROR: Pattern not found")
    # Try to find the log_step_end line
    idx = content.find("log_step_end({i}, 'skipped')")
    if idx >= 0:
        print(f"Found at index {idx}")
        # Print surrounding context
        for i in range(max(0, idx-200), min(len(content), idx+200)):
            if content[i] == '\n':
                break
            print(repr(content[idx-50:idx+100]))
