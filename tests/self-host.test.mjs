import test from 'node:test';
import assert from 'node:assert/strict';
import { assertIndependentConfig, selfHostEnvironment } from '../scripts/self-host.mjs';
const production = { name: 'agent-atlas', account_id: 'a'.repeat(32), routes: [{ pattern: 'agent-id.tagai.fun' }], d1_databases: [{ database_id: 'production-db' }] };
const independent = { name: 'my-atlas', account_id: 'b'.repeat(32), workers_dev: true };
test('self-host accepts an independent account and requires an explicit account for deployment', () => {
  assert.equal(assertIndependentConfig(independent, production, { deploy: true }), independent);
  assert.throws(() => assertIndependentConfig({ name: 'my-atlas' }, production, { deploy: true }));
});
test('self-host rejects production targets, credential vars and ambiguous environments', () => {
  for (const patch of [{ name: production.name }, { account_id: production.account_id },
    { routes: [{ pattern: 'agent-id.tagai.fun' }] }, { routes: [{ pattern: 'AGENT-ID.TAGAI.FUN/*' }] },
    { account_id: production.account_id.toUpperCase() }, { d1_databases: [{ database_id: 'production-db' }] }, { vars: { BSC_RPC_URL: 'https://example.test' } }, { env: { production: {} } }]) {
    assert.throws(() => assertIndependentConfig({ ...independent, ...patch }, production));
  }
});

test('self-host child processes use the explicit account instead of inherited selection', () => {
  const env = selfHostEnvironment(independent, { CLOUDFLARE_ACCOUNT_ID: production.account_id, CF_ACCOUNT_ID: production.account_id, CLOUDFLARE_ENV: 'production' });
  assert.equal(env.CLOUDFLARE_ACCOUNT_ID, independent.account_id);
  assert.equal(env.CF_ACCOUNT_ID, undefined);
  assert.equal(env.CLOUDFLARE_ENV, undefined);
  assert.equal(selfHostEnvironment({ name: 'local' }, env).CLOUDFLARE_ACCOUNT_ID, undefined);
});
