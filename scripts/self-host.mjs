import { readFileSync, copyFileSync, constants } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import JSON5 from 'json5';

const root = fileURLToPath(new URL('../', import.meta.url));
const configPath = path.join(root, 'wrangler.self-host.json');
const builtPath = path.join(root, 'dist/server/wrangler.json');
const read = (p) => JSON.parse(readFileSync(p, 'utf8'));

// Keep the production defaults unchanged. This guard applies only to the new commands.
export function assertIndependentConfig(config, production, { deploy = false } = {}) {
  if (!/^[a-z0-9][a-z0-9-]{0,62}$/.test(config.name || '') || config.name === production.name) {
    throw new Error('Choose a distinct Worker name in wrangler.self-host.json.');
  }
  if (config.account_id && !/^[a-f0-9]{32}$/i.test(config.account_id)) {
    throw new Error('account_id must be your Cloudflare account ID (32 hexadecimal characters).');
  }
  if (config.account_id && config.account_id.toLowerCase() === production.account_id?.toLowerCase()) {
    throw new Error('Self-host commands cannot target the maintained production account.');
  }
  const productionDomains = (production.routes || []).map((r) => typeof r === 'string' ? r : r.pattern);
  for (const route of config.routes || []) {
    const pattern = typeof route === 'string' ? route : route.pattern;
    if (productionDomains.some((domain) => pattern?.toLowerCase().includes(domain.toLowerCase()))) {
      throw new Error('Use your own domain; the maintained production domain is reserved.');
    }
  }
  const productionDatabases = new Set((production.d1_databases || []).map((db) => db.database_id));
  if ((config.d1_databases || []).some((db) => db.database_id && productionDatabases.has(db.database_id))) {
    throw new Error('Use an independent database; production database IDs are reserved.');
  }
  if (config.vars && Object.keys(config.vars).some((k) => /RPC_URL|TOKEN|SECRET|PASSWORD|PRIVATE_KEY/i.test(k))) {
    throw new Error('Store RPC credentials and secrets with Wrangler secrets, not config.vars.');
  }
  if (config.env) throw new Error('Use one explicit self-host configuration; nested environments are not supported.');
  if (deploy && !config.account_id) throw new Error('Set your own account_id before deploying.');
  return config;
}

export function selfHostEnvironment(config, inherited = process.env) {
  const env = { ...inherited, ATLAS_WRANGLER_CONFIG: configPath };
  // An inherited account selection must not redirect an independent deployment.
  delete env.CLOUDFLARE_ACCOUNT_ID;
  delete env.CF_ACCOUNT_ID;
  delete env.CLOUDFLARE_ENV;
  if (config.account_id) env.CLOUDFLARE_ACCOUNT_ID = config.account_id;
  return env;
}

function run(file, args, env) {
  const result = spawnSync(file, args, { cwd: root, env, stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`Command failed (${result.status ?? result.signal}).`);
}

export function main(command) {
  if (!['init', 'dev', 'build', 'preview', 'dry-run', 'deploy'].includes(command)) {
    throw new Error('Expected init, dev, build, preview, dry-run or deploy.');
  }
  if (command === 'init') {
    copyFileSync(path.join(root, 'config/wrangler.self-host.example.json'), configPath, constants.COPYFILE_EXCL);
    console.log('Created wrangler.self-host.json. Set your own Worker name and account_id.');
    return;
  }
  const production = JSON5.parse(readFileSync(path.join(root, 'wrangler.jsonc'), 'utf8'));
  const config = assertIndependentConfig(read(configPath), production, { deploy: command === 'deploy' });
  const env = selfHostEnvironment(config);
  // The source path is absolute so the Vite plugin always resolves the intended config.
  const vinext = path.join(root, 'node_modules/vinext/dist/cli.js');
  if (command === 'dev') { run(process.execPath, [vinext, 'dev', '--port', '5173'], env); return; }
  // Build every time; a production build left in dist can never be reused for deployment.
  run(process.execPath, [vinext, 'build'], env);
  const built = assertIndependentConfig(read(builtPath), production, { deploy: command === 'deploy' });
  for (const key of ['name', 'account_id', 'compatibility_date', 'compatibility_flags', 'workers_dev', 'preview_urls', 'routes', 'd1_databases']) {
    if (JSON.stringify(built[key] ?? (['routes', 'd1_databases'].includes(key) ? [] : null)) !== JSON.stringify(config[key] ?? (['routes', 'd1_databases'].includes(key) ? [] : null))) {
      throw new Error(`Generated configuration does not match self-host ${key}; deployment stopped.`);
    }
  }
  // Detect edits made during the build, without storing or displaying configuration values.
  if (JSON.stringify(read(configPath)) !== JSON.stringify(config)) throw new Error('Config changed during build. Run again.');
  if (command === 'build') return;
  const wrangler = path.join(root, 'node_modules/wrangler/bin/wrangler.js');
  const args = command === 'preview'
    ? ['dev', '--config', builtPath, '--local', '--ip', '127.0.0.1', '--port', '8788', '--inspector-port', '0']
    : ['deploy', '--config', builtPath, '--keep-vars', ...(command === 'dry-run' ? ['--dry-run'] : [])];
  run(process.execPath, ['--import', path.join(root, 'scripts/sites-env.mjs'), wrangler, ...args], env);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { main(process.argv[2]); }
  catch (error) {
    // Avoid printing raw config or credential-bearing upstream error messages.
    console.error(error.code === 'ENOENT' ? 'Configuration or dependency missing. Run self-host:init and install dependencies.'
      : error.code === 'EEXIST' ? 'Local config already exists; it was not overwritten.'
      : error instanceof SyntaxError ? 'Self-host config must be valid JSON.' : error.message);
    process.exitCode = 1;
  }
}
