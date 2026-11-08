import './polyfill.js';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { createYoga } from 'graphql-yoga';
import { schema } from './schema.js';
import { createLoaders } from './loaders.js';

const yoga = createYoga({
  schema,
  context: () => ({
    loaders: createLoaders()
  }),
  graphqlEndpoint: '/graphql',
  landingPage: false
});

const server = createServer(async (req, res) => {
  if (req.url === '/' || req.url === '/index.html') {
    try {
      const html = await readFile(join(process.cwd(), 'public', 'index.html'));
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      return res.end(html);
    } catch (err) {
      res.writeHead(500);
      return res.end('Error al cargar la UI');
    }
  }
  return yoga(req, res);
});

const PORT = process.env.PORT || 4000;
server.listen(PORT, () => {
  console.log(`Gateway ejecutándose en http://localhost:${PORT}`);
  console.log(`GraphiQL Playground en http://localhost:${PORT}/graphql`);
});
