
import logging
import sys
from pathlib import Path

log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)

class LLMLogger:
    def __init__(self, name='llm_interactions'):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        if not self.logger.handlers:
            file_handler = logging.FileHandler(log_dir / 'llm_interactions.log', encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
            self.logger.addHandler(file_handler)
            
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(logging.Formatter('%(asctime)s | %(message)s', datefmt='%H:%M:%S'))
            self.logger.addHandler(console_handler)
    
    def log_request(self, model: str, messages, **kwargs):
        self.logger.info('=' * 80)
        self.logger.info(f'LLM REQUEST | Model: {model}')
        self.logger.debug(f'Messages count: {len(messages)}')
        
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            self.logger.debug(f'--- Message {i+1} [{role.upper()}] ---')
            self.logger.debug(f'Content: {content}')
            self.logger.debug(f'--- End Message {i+1} ---')
        
        total_chars = sum(len(str(msg.get('content', ''))) for msg in messages)
        estimated_tokens = total_chars // 4
        self.logger.info(f'Estimated input tokens: {estimated_tokens}')
    
    def log_response(self, model: str, response, duration_ms: float):
        self.logger.info(f'LLM RESPONSE | Model: {model} | Duration: {duration_ms:.2f}ms')
        
        if hasattr(response, 'content'):
            content = response.content
            self.logger.debug(f'Response content: {content}')
            estimated_tokens = len(content) // 4
            self.logger.info(f'Estimated output tokens: {estimated_tokens}')
        
        if hasattr(response, 'usage'):
            usage = response.usage
            self.logger.info(f'Token usage: prompt_tokens={usage.prompt_tokens}, completion_tokens={usage.completion_tokens}, total_tokens={usage.total_tokens}')
        
        self.logger.info('=' * 80)
    
    def log_error(self, model: str, error: Exception):
        self.logger.error(f'LLM ERROR | Model: {model} | Error: {str(error)}')
        self.logger.error('=' * 80)

llm_logger = LLMLogger()
