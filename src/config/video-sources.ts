/** Deprecated: legacy mp4 video source config.
 *
 * 总览页已改为通过浏览器 MediaDevices API 手动选择本机摄像头/图传采集卡。
 * 该文件暂时保留,避免后续需要回退到视频文件 mock 时丢失路径。
 *
 * 每台机器人的 4 路摄像头视频源配置
 *
 * 数组索引对应视频格子编号：
 *   0 → 1号格(左上)  1 → 2号格(右上)
 *   2 → 3号格(左下)  3 → 4号格(右下)
 *
 * 值为 string 时表示视频 URL，为 null 时显示占位符"加载中..."
 */
export const VIDEO_SOURCES: Record<string, (string | null)[]> = {
  'Hexa-UAV': [
    '/videos/Hexa-UAV-cam1.mp4', // 1号格 - 左上 - 播放真实视频
    null, // 2号格 - 右上
    null, // 3号格 - 左下
    null // 4号格 - 右下
  ],
  'Quadri-UAV': [null, null, null, null],
  'MricoCV-USV': [null, null, null, null],
  'CL-USV': [null, null, null, null]
}

/** 摄像头标签 */
export const CAMERA_LABELS = ['CAM-1', 'CAM-2', 'CAM-3', 'CAM-4'] as const
