import logging
import sys
from pathlib import Path

# 创建日志目录
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# 创建 LLM 日志配置
class LLMLogger:
    \"\"\"LLM交互日志记录器\"\"\"
    
    def __init__(self, name: str = "llm_interactions"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # 避免重复添加handler
        if not self.logger.handlers:
            # 文件handler - 记录所有LLM交互
            file_handler = logging.FileHandler(
                log_dir / "llm_interactions.log",
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '%(asctime)s | %(levelname)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
            
            # 控制台handler - 只显示关键信息
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(
                '%(asctime)s | %(message)s',
                datefmt='%H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
    
    def log_request(self, model: str, messages: List[Dict], **kwargs):
        \"\"\"记录LLM请求\"\"\"
        self.logger.info(f\"=\" * 80)
        self.logger.info(f\"LLM REQUEST | Model: {model}\")
        self.logger.debug(f\"Messages count: {len(messages)}\")
        self.logger.debug(f\"Additional params: {kwargs}\")
        
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            self.logger.debug(f\"--- Message {i+1} [{role.upper()}] ---\")
            self.logger.debug(f\"Content: {content}\")
            self.logger.debug(f\"--- End Message {i+1} ---\")
        
        # 计算prompt tokens（估算）
        total_chars = sum(len(str(msg.get('content', ''))) for msg in messages)
        estimated_tokens = total_chars // 4  # 粗略估算：1 token ≈ 4 characters
        self.logger.info(f\"Estimated input tokens: {estimated_tokens}\")
    
    def log_response(self, model: str, response: Any, duration_ms: float):
        \"\"\"记录LLM响应\"\"\"
        self.logger.info(f\"LLM RESPONSE | Model: {model} | Duration: {duration_ms:.2f}ms\")
        
        if hasattr(response, 'content'):
            content = response.content
            self.logger.debug(f\"Response content:\")
            self.logger.debug(f\"{content}\")
            
            # 计算输出tokens（估算）
            estimated_tokens = len(content) // 4
            self.logger.info(f\"Estimated output tokens: {estimated_tokens}\")
        
        if hasattr(response, 'usage'):
            usage = response.usage
            self.logger.info(f\"Token usage: prompt_tokens={usage.prompt_tokens}, completion_tokens={usage.completion_tokens}, total_tokens={usage.total_tokens}\")
        
        self.logger.info(f\"=\" * 80)
    
    def log_error(self, model: str, error: Exception):
        \"\"\"记录LLM错误\"\"\"
        self.logger.error(f\"LLM ERROR | Model: {model} | Error: {str(error)}\")
        self.logger.error(f\"=\" * 80)


# 创建全局LLM日志实例
llm_logger = LLMLogger()
