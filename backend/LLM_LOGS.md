# LLM 交互日志说明

## 日志位置

LLM 交互日志存储在: ackend/logs/llm_interactions.log

## 日志格式

每个 LLM 交互包含以下信息：

### 请求信息
- 请求时间
- 使用的模型 (qwen-plus / qwen-vl-plus)
- 请求方法 (generate_text / recognize_captcha / analyze_page_for_captcha)
- 消息数量
- 估算的输入 tokens
- 完整的 prompt 内容（DEBUG级别）

### 响应信息
- 响应时间
- 响应内容（DEBUG级别）
- 估算的输出 tokens
- Token 使用情况（如果 API 返回）

### 错误信息
- 错误详情

## 查看日志

### 查看所有日志
`ash
cat backend/logs/llm_interactions.log
`

### 查看最近的日志
`ash
tail -f backend/logs/llm_interactions.log
`

### 查看最近的 100 行
`ash
tail -n 100 backend/logs/llm_interactions.log
`

### 搜索特定模型的日志
`ash
grep \"qwen-plus\" backend/logs/llm_interactions.log
grep \"qwen-vl-plus\" backend/logs/llm_interactions.log
`

### 搜索错误日志
`ash
grep \"LLM ERROR\" backend/logs/llm_interactions.log
`

## 日志级别

- **INFO**: 显示在控制台和文件中（摘要信息）
  - 请求开始
  - 模型名称
  - 估算的 tokens
  - 响应完成
  - Token 使用情况
  
- **DEBUG**: 仅显示在文件中（详细信息）
  - 完整的 prompt 内容
  - 完整的响应内容
  - 消息详情

## 示例日志输出

`
2026-02-07 11:30:15 | INFO | ================================================================================
2026-02-07 11:30:15 | INFO | LLM REQUEST | Model: qwen-plus
2026-02-07 11:30:15 | DEBUG | Messages count: 2
2026-02-07 11:30:15 | DEBUG | Additional params: {'method': 'generate_text'}
2026-02-07 11:30:15 | DEBUG | --- Message 1 [SYSTEM] ---
2026-02-07 11:30:15 | DEBUG | Content: 你是一个端到端测试专家。你的目标是将通用的业务端到端测试任务分解为更小的、明确定义的操作...
2026-02-07 11:30:15 | DEBUG | --- End Message 1 ---
2026-02-02 11:30:15 | DEBUG | --- Message 2 [USER] ---
2026-02-07 11:30:15 | DEBUG | Content: 将以下输入转换为包含"actions"键和原子步骤列表作为值的JSON字典...
2026-02-07 11:30:15 | DEBUG | --- End Message 2 ---
2026-02-07 11:30:15 | INFO | Estimated input tokens: 1234
2026-02-07 11:30:18 | INFO | LLM RESPONSE | Model: qwen-plus | Duration: 2345.67ms
2026-02-07 11:30:18 | DEBUG | Response content:
2026-02-07 11:30:18 | DEBUG | {\"actions\": [\"导航到登录页面...\", \"输入用户名...\", ...]}
2026-02-07 11:30:18 | INFO | Estimated output tokens: 567
2026-02-07 11:30:18 | INFO | Token usage: prompt_tokens=1234, completion_tokens=567, total_tokens=1801
2026-02-07 11:30:18 | INFO | ================================================================================
`

## Token 使用统计

由于百练平台 API 可能不返回详细的 token 使用信息，系统会进行估算：
- 输入 tokens ≈ 总字符数 / 4
- 输出 tokens ≈ 响应字符数 / 4

如果 API 返回了实际的 token 使用信息，将使用实际数据。

## 日志文件管理

- 日志文件会自动创建在 ackend/logs/ 目录
- 建议定期清理或归档旧的日志文件
- 可以使用日志轮转工具（如 logrotate）管理日志文件大小
