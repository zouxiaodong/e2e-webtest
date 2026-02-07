-- 为 test_scenarios 表添加缺失的字段
ALTER TABLE test_scenarios ADD COLUMN login_config VARCHAR(50) DEFAULT 'no_login' COMMENT '登录配置';
ALTER TABLE test_scenarios ADD COLUMN session_id INT COMMENT '关联的会话ID';
ALTER TABLE test_scenarios ADD COLUMN save_session BOOLEAN DEFAULT FALSE COMMENT '是否保存会话';