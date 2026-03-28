import html

def escape_html(text: str) -> str:
    return html.escape(str(text), quote=False)

test_cases = [
    "Race & Sprint",
    "Driver <NAME>",
    "Finish > Start",
    "Already *formatted* with Markdown",
    "Special_Character_Test"
]

print("HTML Escaping Results:")
for tc in test_cases:
    print(f"Original: {tc}")
    print(f"Escaped:  {escape_html(tc)}")
    print("-" * 20)

# Check if <b> and <i> tags are used correctly in a mock message
print("\nMock Message:")
greeting = f"🌅 <b>Good morning!</b>\n<i>Saturday, March 28, 2026</i>"
section = f"📋 <b>LINEAR TASKS</b>\n- {escape_html('Fix & Test')} [Priority: {escape_html('High')}]"
print(greeting)
print(section)
