"""
Fix scenarios.py syntax error
"""
# Read the file
with open('D:/researches/e2etest/backend/app/api/scenarios.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the broken code
old_code = '''                # Convert case_type string to enum
case_type_str = case_data.get("case_type", "positive").upper()
try:
    case_type = TestCaseType[case_type_str]
except KeyError:
    case_type = TestCaseType.POSITIVE
case_type=case_type,'''

new_code = '''                # Convert case_type string to enum
                case_type_str = case_data.get("case_type", "positive").upper()
                try:
                    case_type = TestCaseType[case_type_str]
                except KeyError:
                    case_type = TestCaseType.POSITIVE'''

content = content.replace(old_code, new_code)

# Write the file back
with open('D:/researches/e2etest/backend/app/api/scenarios.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done! Fixed syntax error")
