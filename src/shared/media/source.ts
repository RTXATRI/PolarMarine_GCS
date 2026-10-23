export interface MediaSource {
  readonly kind: string
  start(): Promise<MediaStream>
  stop(): void
}

export class LocalUvcSource implements MediaSource {
  readonly kind = 'local-uvc'
  private stream: MediaStream | null = null
  private generation = 0

  constructor(private readonly browserDeviceId: string) {}

  async start(): Promise<MediaStream> {
    this.releaseTracks()
    const generation = ++this.generation
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { deviceId: { exact: this.browserDeviceId } },
      audio: false
    })
    if (generation !== this.generation) {
      stream.getTracks().forEach((track) => track.stop())
      throw new DOMException('Camera request was superseded', 'AbortError')
    }
    this.stream = stream
    return stream
  }

  stop(): void {
    this.generation += 1
    this.releaseTracks()
  }

  private releaseTracks(): void {
    this.stream?.getTracks().forEach((track) => track.stop())
    this.stream = null
  }
}

export function mediaErrorMessage(reason: unknown): string {
  if (!(reason instanceof DOMException)) return '无法打开本机摄像头'
  if (reason.name === 'AbortError') return ''
  if (reason.name === 'NotAllowedError') return '摄像头授权被拒绝'
  if (reason.name === 'NotReadableError') return '摄像头正被其他程序占用'
  if (reason.name === 'NotFoundError') return '绑定的摄像头已拔出或不存在'
  return reason.message || '摄像头打开失败'
}

export interface FutureWebRtcSource extends MediaSource {
  readonly kind: 'webrtc'
}

export interface FuturePlaybackSource extends MediaSource {
  readonly kind: 'playback'
}
