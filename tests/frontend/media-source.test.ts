import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LocalUvcSource, mediaErrorMessage } from '@/shared/media/source'

describe('LocalUvcSource', () => {
  const stop = vi.fn()
  const stream = { getTracks: () => [{ stop }] } as unknown as MediaStream
  const getUserMedia = vi.fn(async () => stream)

  beforeEach(() => {
    stop.mockClear()
    getUserMedia.mockClear()
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia }
    })
  })

  it('binds an exact workstation camera and releases every track', async () => {
    const source = new LocalUvcSource('camera-a')
    expect(await source.start()).toBe(stream)
    expect(getUserMedia).toHaveBeenCalledWith({
      video: { deviceId: { exact: 'camera-a' } },
      audio: false
    })
    source.stop()
    expect(stop).toHaveBeenCalledOnce()
  })

  it('releases a delayed stream that arrives after an offline cancellation', async () => {
    let resolveStream: (value: MediaStream) => void = () => undefined
    getUserMedia.mockImplementationOnce(
      () => new Promise<MediaStream>((resolve) => (resolveStream = resolve))
    )
    const source = new LocalUvcSource('camera-a')
    const pending = source.start()
    source.stop()
    resolveStream(stream)
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
    expect(stop).toHaveBeenCalledOnce()
  })

  it('maps browser permission, occupancy and unplug errors to operator messages', () => {
    expect(mediaErrorMessage(new DOMException('', 'NotAllowedError'))).toBe('摄像头授权被拒绝')
    expect(mediaErrorMessage(new DOMException('', 'NotReadableError'))).toBe(
      '摄像头正被其他程序占用'
    )
    expect(mediaErrorMessage(new DOMException('', 'NotFoundError'))).toBe(
      '绑定的摄像头已拔出或不存在'
    )
  })
})
