import re

with open("app.py", "r", encoding="utf-8") as f:
    text = f.read()

pattern = r'(st\.(?:markdown|html)\(\s*(?:f?"""|f?\'\'\')(.*?)(?:"""|\'\'\'))'
for m in re.finditer(pattern, text, re.DOTALL):
    inner = m.group(2)
    if '<div' in inner:
        lineno = text[:m.start()].count('\n') + 1
        print(f"Line {lineno}: {inner.strip()[:80]}")

