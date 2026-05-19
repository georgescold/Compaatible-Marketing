const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const src = 'Knowledges/_ogilvy_epub_extract/book.zip';
const dest = 'Knowledges/_ogilvy_epub_extract/';

// Read entire file
const buf = fs.readFileSync(src);

// Parse ZIP central directory
// Find End of Central Directory Record
function findEOCD(buf) {
    const sig = Buffer.from([0x50, 0x4b, 0x05, 0x06]);
    for (let i = buf.length - 22; i >= Math.max(0, buf.length - 65557); i--) {
        if (buf[i] === 0x50 && buf[i+1] === 0x4b && buf[i+2] === 0x05 && buf[i+3] === 0x06) {
            return i;
        }
    }
    return -1;
}

const eocdPos = findEOCD(buf);
if (eocdPos < 0) { console.error('EOCD not found'); process.exit(1); }

const numEntries = buf.readUInt16LE(eocdPos + 10);
const cdSize = buf.readUInt32LE(eocdPos + 12);
const cdOffset = buf.readUInt32LE(eocdPos + 16);

console.log('Entries:', numEntries, 'CD offset:', cdOffset);

const entries = [];
let p = cdOffset;
for (let i = 0; i < numEntries; i++) {
    if (buf.readUInt32LE(p) !== 0x02014b50) { console.error('Bad CD sig at', p); break; }
    const method = buf.readUInt16LE(p + 10);
    const compSize = buf.readUInt32LE(p + 20);
    const uncompSize = buf.readUInt32LE(p + 24);
    const nameLen = buf.readUInt16LE(p + 28);
    const extraLen = buf.readUInt16LE(p + 30);
    const commentLen = buf.readUInt16LE(p + 32);
    const localHeaderOffset = buf.readUInt32LE(p + 42);
    const name = buf.slice(p + 46, p + 46 + nameLen).toString('utf8');
    entries.push({ name, method, compSize, uncompSize, localHeaderOffset });
    p += 46 + nameLen + extraLen + commentLen;
}

for (const e of entries) {
    if (e.name.endsWith('/')) continue;
    // Read local header
    let lp = e.localHeaderOffset;
    if (buf.readUInt32LE(lp) !== 0x04034b50) { console.error('Bad local sig'); continue; }
    const lnameLen = buf.readUInt16LE(lp + 26);
    const lextraLen = buf.readUInt16LE(lp + 28);
    const dataStart = lp + 30 + lnameLen + lextraLen;
    const data = buf.slice(dataStart, dataStart + e.compSize);

    let outData;
    if (e.method === 0) {
        outData = data;
    } else if (e.method === 8) {
        outData = zlib.inflateRawSync(data);
    } else {
        console.error('Unknown method', e.method, 'for', e.name); continue;
    }

    const outPath = path.join(dest, e.name);
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, outData);
    console.log('Extracted:', e.name, '(' + outData.length + ' bytes)');
}

console.log('Done, total entries:', entries.length);
