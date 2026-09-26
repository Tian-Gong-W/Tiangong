import express from 'express';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const app = express();
const port = Number(process.env.PORT || 3000);
const root = path.dirname(fileURLToPath(import.meta.url));
const dist = path.join(root, 'dist');

app.disable('x-powered-by');
app.use(express.static(dist, { index: 'index.html', maxAge: '1h' }));
app.get('*', (_request, response) => {
  response.sendFile(path.join(dist, 'index.html'));
});

app.listen(port, '0.0.0.0', () => {
  console.log(`Tonmen AI Mission Control listening on ${port}`);
});
