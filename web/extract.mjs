import fs from 'node:fs';
import AdmZip from 'adm-zip';

const source = new URL('./topmen-one-ready.zip', import.meta.url);
const target = new URL('./app/', import.meta.url);

fs.rmSync(target, { recursive: true, force: true });
fs.mkdirSync(target, { recursive: true });
new AdmZip(source.pathname).extractAllTo(target.pathname, true);
console.log('Extracted TianGong web bundle to web/app');
