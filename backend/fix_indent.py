import sys
sys.path.insert(0, r'D:\researches\e2etest\backend')

with open(r'D:\researches\e2etest\backend\app\services\executor\test_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix: except should be at SAME indentation as try (16 spaces), not 24
old = """                            code_lines.append(f"                except Exception as e:")
                            code_lines.append(f"                    log_step_end({i}, 'failed', error_message=str(e))")
                            code_lines.append(f"                    raise")"""

new = """                        code_lines.append(f"                except Exception as e:")
                        code_lines.append(f"                    log_step_end({i}, 'failed', error_message=str(e))")
                        code_lines.append(f"                    raise")"""

if old in content:
    content = content.replace(old, new)
    with open(r'D:\researches\e2etest\backend\app\services\executor\test_executor.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed indentation!")
else:
    print("Pattern not found")
