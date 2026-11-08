import assert from 'node:assert';
import test from 'node:test';
import { createLoaders } from '../src/loaders.js';
import { schema } from '../src/schema.js';
import { graphql } from 'graphql';

test('DataLoader inicializa correctamente los loaders', () => {
  const loaders = createLoaders();
  assert.ok(loaders.userLoader, 'Debe existir userLoader');
  assert.ok(loaders.gamificationLoader, 'Debe existir gamificationLoader');
});

test('Schema GraphQL responde la consulta de canales sin colapsar', async () => {
  const query = `
    query {
      channels {
        id
        name
      }
    }
  `;

  const response = await graphql({
    schema,
    source: query,
    contextValue: {
      loaders: createLoaders()
    }
  });

  assert.strictEqual(response.errors, undefined, 'No deben ocurrir errores de sintaxis en el esquema');
  assert.ok(Array.isArray(response.data.channels), 'channels debe retornar una lista');
});
