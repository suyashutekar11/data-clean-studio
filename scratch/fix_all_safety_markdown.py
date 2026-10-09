with open("app.py", "r", encoding="utf-8") as f:
    text = f.read()

# Replace st.markdown with render_html on lines 1967, 3306, 3488, 3542
old_1967 = '''    if not profile_data:
        st.markdown(
            f"""
            <div class="safety-banner"'''
new_1967 = '''    if not profile_data:
        render_html(
            f"""
            <div class="safety-banner"'''
assert old_1967 in text
text = text.replace(old_1967, new_1967, 1)

old_3306 = '''                        num_existing = len(existing_tbl_workspaces)
                        st.markdown(
                            f"""
                            <div class="safety-banner"'''
new_3306 = '''                        num_existing = len(existing_tbl_workspaces)
                        render_html(
                            f"""
                            <div class="safety-banner"'''
assert old_3306 in text
text = text.replace(old_3306, new_3306, 1)

old_3488 = '''                    else:
                        st.markdown(
                            f"""
                            <div class="safety-banner" style="margin-bottom: 1rem;">'''
new_3488 = '''                    else:
                        render_html(
                            f"""
                            <div class="safety-banner" style="margin-bottom: 1rem;">'''
assert old_3488 in text
text = text.replace(old_3488, new_3488, 1)

old_3542 = '''                    # Sandbox Guarantee Banner
                    # ---------------------------------------------
                    st.markdown(
                        f"""
                        <div class="safety-banner">'''
new_3542 = '''                    # Sandbox Guarantee Banner
                    # ---------------------------------------------
                    render_html(
                        f"""
                        <div class="safety-banner">'''
assert old_3542 in text
text = text.replace(old_3542, new_3542, 1)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(text)

print("All safety-banner st.markdown calls replaced with render_html")

