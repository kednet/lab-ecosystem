import os, sys, yaml
os.environ["PYTHONIOENCODING"] = "utf-8"
for f in ['zolotye-pravila-ispolneniya-zhelaniy', 'malenkie-shagi', 'chuvstvo-ispolnennogo-zhelaniya', 'rabota-s-vnutrennim-kritikom', 'utrennee-namerenie']:
    print(f"===== {f} =====")
    d = yaml.safe_load(open(f'data/library/{f}.yaml', encoding='utf-8'))
    s = d.get('script', '')
    lines = [l for l in s.split('\n') if l.strip()]
    print('  Всего строк:', len(lines))
    print('  Первые 4:')
    for l in lines[:4]: print('   >', l)
    print('  Последние 6:')
    for l in lines[-6:]: print('   >', l)
    print()
