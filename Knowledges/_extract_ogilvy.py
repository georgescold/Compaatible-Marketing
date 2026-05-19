import zipfile, os, sys
src = r'C:\Users\loysc\Desktop\Compaatible marketing\Knowledges\Ogilvy on Advertising (David Ogilvy) (z-library.sk, 1lib.sk, z-lib.sk).epub'
dest = r'C:\Users\loysc\Desktop\Compaatible marketing\Knowledges\_ogilvy_epub_extract'
os.makedirs(dest, exist_ok=True)
with zipfile.ZipFile(src) as z:
    z.extractall(dest)
    names = z.namelist()
print('Extracted', len(names), 'files')
for n in names:
    print(n)
