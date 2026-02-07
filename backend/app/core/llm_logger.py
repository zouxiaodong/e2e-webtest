
import logging
import sys
import re
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
    
    def _truncate_content(self, content, max_length=100):
        """截断内容，对于长内容只显示前max_length个字符"""
        content_str = str(content)
        if len(content_str) > max_length:
            return content_str[:max_length] + f'... [truncated, total {len(content_str)} chars]'
        return content_str
    
    def _truncate_base64_in_html(self, content):
        """截断HTML内容中的base64图片数据"""
        content_str = str(content)
        # 匹配 base64 图片数据：data:image/xxx;base64,xxxx
        pattern = r'(data:image/[^;]+;base64,)([A-Za-z0-9+/=]{100,})'
        
        def replace_base64(match):
            prefix = match.group(1)
            base64_data = match.group(2)
            return f'{prefix}{base64_data[:10]}... [base64 truncated, total {len(base64_data)} chars]'
        
        return re.sub(pattern, replace_base64, content_str)

    def _is_html_content(self, content):
        """判断内容是否为HTML"""
        content_str = str(content)
        # 如果内容包含HTML标签特征，认为是HTML
        return ('<' in content_str and '>' in content_str and 
                ('</' in content_str or '/>' in content_str or '<html' in content_str.lower()))

    def log_request(self, model: str, messages, **kwargs):
        self.logger.info('=' * 80)
        self.logger.info(f'LLM REQUEST | Model: {model}')
        self.logger.debug(f'Messages count: {len(messages)}')
        
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            self.logger.debug(f'--- Message {i+1} [{role.upper()}] ---')
            
            # 处理多模态内容（包含图片）
            if isinstance(content, list):
                # 多模态消息，content是列表
                truncated_content = []
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'image_url':
                        # 图片内容，只显示前100个字符
                        image_url = item.get('image_url', {}).get('url', '')
                        truncated_content.append({
                            'type': 'image_url',
                            'url': self._truncate_content(image_url, 100)
                        })
                    else:
                        # 文本内容
                        truncated_content.append(item)
                self.logger.debug(f'Content: {truncated_content}')
            elif self._is_html_content(content):
                # HTML内容，只输出长度信息，不输出具体内容
                content_length = len(content)
                # 统计base64图片数量
                base64_count = len(re.findall(r'data:image/[^;]+;base64,', content))
                self.logger.debug(f'Content: [HTML content, length: {content_length} chars, base64 images: {base64_count}]')
            else:
                # 普通文本内容
                self.logger.debug(f'Content: {self._truncate_content(content, 500)}')
            
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
