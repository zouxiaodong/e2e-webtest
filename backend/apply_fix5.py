import sys
sys.path.insert(0, r'D:\researches\e2etest\backend')

with open(r'D:\researches\e2etest\backend\app\services\executor\test_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Current broken pattern
old = """                            code_lines.append(f"                    log_step_end({i}, 'skipped')")
                            except Exception as e:
                                code_lines.append(f"                    log_step_end({i}, 'failed', error_message=str(e))")
                                code_lines.append(f"                    raise")
                        else:"""

# Fixed pattern - except at 24 spaces (same as try), log_step_end inside at 24 spaces, raise at 24 spaces
new = """                            code_lines.append(f"                    log_step_end({i}, 'skipped')")
                        except Exception as e:
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
