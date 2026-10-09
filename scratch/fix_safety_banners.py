import re

with open("app.py", "r", encoding="utf-8") as f:
    text = f.read()

# Replace any st.html(...) calls that render safety banners with render_html(...)
# In line 4279 and 4290
text = text.replace(
    'st.html(\n                                            f"""\n                                            <div class="safety-banner"',
    'render_html(\n                                            f"""\n                                            <div class="safety-banner"'
)
text = text.replace(
    'st.html(\n                                            f"""\n                                            <div class="safety-banner"',
    'render_html(\n                                            f"""\n                                            <div class="safety-banner"'
)

# Also check any other st.html calls in app.py
st_html_count = text.count('st.html(')
print(f"Remaining st.html calls: {st_html_count}")

with open("app.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Safety banner st.html replaced with render_html")

