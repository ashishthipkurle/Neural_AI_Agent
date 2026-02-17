import hashlib, sys
path = r'D:\All Projects\My AI Agent\README.md'
with open(path, 'rb') as f:
    data = f.read()
hash_val = hashlib.sha256(data).hexdigest()
with open(r'D:\All Projects\My AI Agent\hash_original.txt', 'w') as out:
    out.write(hash_val)
print('Hash written')
