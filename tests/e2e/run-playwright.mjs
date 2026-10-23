/* global process */
import { spawn } from 'node:child_process'
import { rm } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath, URL } from 'node:url'
import { createServer } from 'vite'

const repositoryRoot = fileURLToPath(new URL('../..', import.meta.url))
const chromiumDebugLog = join(repositoryRoot, 'debug.log')
const playwrightCli = fileURLToPath(
  new URL('../../node_modules/@playwright/test/cli.js', import.meta.url)
)
process.env.CHROME_LOG_FILE ??= process.platform === 'win32' ? 'NUL' : '/dev/null'
await rm(chromiumDebugLog, { force: true })
const server = await createServer({
  root: repositoryRoot,
  server: { host: '127.0.0.1', port: 5173, strictPort: true }
})
let child = null

async function shutdown() {
  if (child && child.exitCode == null) child.kill('SIGTERM')
  try {
    await server.close()
  } finally {
    await rm(chromiumDebugLog, { force: true })
  }
}

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.once(signal, () => {
    void shutdown().finally(() => process.exit(1))
  })
}

let exitCode
try {
  await server.listen()
  child = spawn(process.execPath, [playwrightCli, 'test', ...process.argv.slice(2)], {
    cwd: repositoryRoot,
    env: process.env,
    stdio: 'inherit'
  })
  exitCode = await new Promise((resolve, reject) => {
    child.once('error', reject)
    child.once('exit', (code) => resolve(code ?? 1))
  })
} finally {
  await shutdown()
}

process.exitCode = exitCode
