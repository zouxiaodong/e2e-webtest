"""
Fix script to convert case_type string to enum
"""
# Read the file
with open('D:/researches/e2etest/backend/app/api/scenarios.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add import for TestCaseType
old_import = 'from ..models.test_case import TestScenario, TestCase, TestReport, TestStepResult'
new_import = 'from ..models.test_case import TestScenario, TestCase, TestReport, TestStepResult, TestCaseType'

content = content.replace(old_import, new_import)

# 2. Fix the case_type conversion
old_code = '''case_type=case_data.get("case_type", "positive"),'''
new_code = '''# Convert case_type string to enum
case_type_str = case_data.get("case_type", "positive").upper()
try:
    case_type = TestCaseType[case_type_str]
except KeyError:
    case_type = TestCaseType.POSITIVE
case_type=case_type,'''

content = content.replace(old_code, new_code)

# Write the file back
with open('D:/researches/e2etest/backend/app/api/scenarios.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done! Fixed case_type enum conversion")
