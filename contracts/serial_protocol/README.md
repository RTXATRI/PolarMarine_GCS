# PolarMarine Serial JSON v1

每条记录格式为：

```text
0x1E + compact UTF-8 JSON + 0x09 + 8位大写CRC32 + 0x0A
```

CRC32 仅覆盖 JSON 原始字节；JSON 最大 32 KiB。接收器在半包时等待，在粘包时逐条解析；遇到噪声、非法 UTF-8、超长或 CRC 错误时丢弃当前记录并扫描下一个 `0x1E`。JSON 必须符合 [设备消息信封](../device_protocol/message-envelope.schema.json)。

序号为无符号 32 位整数。`0xFFFFFFFF → 0` 是合法回绕；重复或反向序号不得覆盖较新的遥测。命令重试必须复用原 `commandId`，由设备端去重。
