const configuredApiBase = import.meta.env.VITE_GCS_API_BASE?.trim()
const apiBase = (configuredApiBase || '/api/v1').replace(/\/$/, '')

function websocketUrl(): string {
  const configured = import.meta.env.VITE_GCS_WS_URL?.trim()
  if (configured) return configured
  const base = new URL(apiBase, window.location.origin)
  base.protocol = base.protocol === 'https:' ? 'wss:' : 'ws:'
  base.pathname = base.pathname.replace(/\/$/, '') + '/events'
  return base.toString()
}

export const runtimeConfig = Object.freeze({
  apiBase,
  websocketUrl: websocketUrl()
})
