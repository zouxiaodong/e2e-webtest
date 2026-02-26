import sys
sys.path.insert(0, r'D:\researches\e2etest\backend')

# Read the file
with open(r'D:\researches\e2etest\backend\app\services\executor\test_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the incorrect "else:" line that was causing the syntax error
# It's after the except block and is incorrectly placed
old_text = """                        except Exception as e:
                            code_lines.append(f"                    log_step_end({i}, 'failed', error_message=str(e))")
                            code_lines.append(f"                    raise")
                        else:"""

new_text = """                        except Exception as e:
                            code_lines.append(f"                    log_step_end({i}, 'failed', error_message=str(e))")
                            code_lines.append(f"                    raise")"""

if old_text in content:
    content = content.replace(old_text, new_text)
    with open(r'D:\researches\e2etest\backend\app\services\executor\test_executor.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: Removed incorrect else!")
else:
    print("ERROR: Pattern not found")
