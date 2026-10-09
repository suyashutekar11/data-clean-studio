import pathlib

js_file = pathlib.Path(r'C:\Users\Admin\AppData\Roaming\Python\Python314\site-packages\streamlit\static\static\js\index.ByR4Z2EF.js')
txt = js_file.read_text(encoding='utf-8')

for var_name in ['Pm', 'Cm']:
    idx = txt.find(f'{var_name}=')
    if idx != -1:
        print(f"=== {var_name} ===")
        print(txt[idx:idx+300])
    else:
        print(f"{var_name}= not found")

