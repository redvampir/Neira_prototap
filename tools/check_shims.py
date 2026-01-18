from pathlib import Path
root=Path('.').resolve()
scripts=root/'scripts'
missing=[]
for p in sorted(scripts.glob('*.py')):
    if not (root/p.name).exists():
        missing.append(p.name)
print('Missing shims count:', len(missing))
for m in missing:
    print(m)
