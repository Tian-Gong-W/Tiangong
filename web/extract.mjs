import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import AdmZip from 'adm-zip';

const root = path.dirname(fileURLToPath(import.meta.url));
const target = path.join(root, 'app');
const zipPath = path.join(root, 'web-bundle.zip');
const expectedSha256 = 'b7c2bed503182db764035f35cc41a44ef92e3ff01e992c1038dfa58994f66508';

const parts = fs.readdirSync(root)
  .filter((name) => /^bundle\.part\d+\.b64$/.test(name))
  .sort();

if (parts.length !== 8) {
  throw new Error(`Expected 8 bundle parts, found ${parts.length}`);
}

const encoded = parts
  .map((name) => fs.readFileSync(path.join(root, name), 'utf8').trim())
  .join('');

const zipBuffer = Buffer.from(encoded, 'base64');
const actualSha256 = crypto.createHash('sha256').update(zipBuffer).digest('hex');

if (actualSha256 !== expectedSha256) {
  throw new Error(`Bundle SHA-256 mismatch: expected ${expectedSha256}, got ${actualSha256}`);
}

fs.writeFileSync(zipPath, zipBuffer);
fs.rmSync(target, { recursive: true, force: true });
fs.mkdirSync(target, { recursive: true });
new AdmZip(zipBuffer).extractAllTo(target, true);

console.log(`Verified and extracted ${zipBuffer.length} byte TianGong web bundle from ${parts.length} parts`);
