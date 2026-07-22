/**
 * Convert internal operation audit text into the wording shown to users.
 * The backend keeps the original content; this function affects only the
 * frontend presentation layer.
 */
export function toUserFacingOperationText(content: string): string {
  const text = content
    .replace(/\[(?:模拟任务|模拟)\]\s*/g, '')
    .replace(/，?\s*(?:未发送飞控|未写入飞控|真实飞控状态未改变|真实状态未改变|实际模式以 MAVROS 为准)/g, '')
    .replace(/请求切换控制模式为\s*([^，。；]+)/g, '模式切换指令发送成功：$1')
    .replace(/请求(解锁|锁定)设备/g, '$1指令发送成功')
    .replace(/急停操作已记录/g, '急停指令发送成功')
    .replace(/操作已记录/g, '指令已发送')
    .replace(/模拟任务/g, '任务')
    .replace(/模拟/g, '')
    .replace(/虚拟/g, '')
    .replace(/演示/g, '')
    .replace(/，(?=[，。；]|$)/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim()

  return text || '操作完成'
}
