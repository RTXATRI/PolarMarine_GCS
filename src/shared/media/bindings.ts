const DATABASE = 'polarmarine-gcs-workstation'
const STORE = 'media-bindings'

export interface MediaBinding {
  key: string
  browserDeviceId: string
  label: string
}

export const bindingKey = (deviceId: string, channelId: string): string =>
  deviceId + ':' + channelId

export async function readBinding(key: string): Promise<MediaBinding | null> {
  const database = await openDatabase()
  return new Promise<MediaBinding | null>((resolve, reject) => {
    const transaction = database.transaction(STORE, 'readonly')
    const request = transaction.objectStore(STORE).get(key)
    request.onsuccess = () => resolve((request.result as MediaBinding | undefined) ?? null)
    request.onerror = () => reject(request.error)
  }).finally(() => database.close())
}

export async function writeBinding(binding: MediaBinding): Promise<void> {
  const database = await openDatabase()
  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction(STORE, 'readwrite')
    transaction.objectStore(STORE).put(binding)
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => reject(transaction.error)
  })
  database.close()
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1)
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE))
        request.result.createObjectStore(STORE, { keyPath: 'key' })
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}
