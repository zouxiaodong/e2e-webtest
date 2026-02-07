# 测试会话管理方案

## 问题分析

当前每个测试场景都需要执行登录，导致：
- 测试效率低（重复登录）
- Token 消耗大（每次登录都调用 LLM）
- 测试时间长

## 解决方案

### 方案架构

提供多层级会话管理：

`
全局会话（可选）
    ↓
场景级会话
    ↓
用例级会话
`

### 登录配置选项

在创建/编辑场景时，提供以下登录配置选项：

1. **不需要登录** - 
o_login
   - 适用于公开页面、注册页面等

2. **执行登录** - perform_login
   - 执行完整的登录流程
   - 可选择是否保存会话供后续使用

3. **使用全局会话** - use_global_session
   - 使用系统保存的全局登录会话
   - 快速跳过登录步骤

4. **使用指定会话** - use_session
   - 使用之前保存的特定会话
   - 可选择哪个会话

### 会话保存时机

- 执行登录场景后，可选择保存会话
- 保存内容包括：
  - Cookies（认证 token 等）
  - localStorage（用户信息等）
  - sessionStorage（临时数据）

### 会话有效期

- 默认有效期：24 小时
- 可配置
- 过期后自动失效

## 实现细节

### 1. 数据模型

已创建 TestSession 模型：

`python
class TestSession(Base):
    \"\"\"测试会话模型\"\"\"
    id: 主键
    name: 会话名称
    description: 会话描述
    cookies: Cookies 数据
    local_storage: localStorage 数据
    session_storage: sessionStorage 数据
    target_url: 目标 URL
    login_scenario_id: 关联的登录场景 ID
    is_active: 是否活跃
    expires_at: 过期时间
    created_at: 创建时间
    last_used_at: 最后使用时间
`

### 2. 场景模型更新

TestScenario 模型已添加登录配置字段：

`python
class TestScenario(Base):
    login_config: 登录配置（no_login / perform_login / use_global_session / use_session）
    session_id: 使用的会话 ID
    save_session: 是否保存会话
`

### 3. 会话管理服务

已创建 SessionManager 服务，提供以下功能：

- save_session(page, name, description) - 保存会话
- estore_session(page, session_data) - 恢复会话
- clear_session(page) - 清除会话
- is_session_expired(session_data) - 检查会话是否过期
- get_session_summary(session_data) - 获取会话摘要

### 4. 测试执行流程

`
场景执行开始
    ↓
检查登录配置
    ↓
    ├─ no_login → 直接执行测试
    ├─ perform_login → 执行登录 → 可选保存会话 → 执行测试
    ├─ use_global_session → 恢复全局会话 → 执行测试
    └─ use_session → 恢复指定会话 → 执行测试
    ↓
测试完成
    ↓
可选：保存会话
`

## 使用流程

### 方案 A：全局会话（推荐用于频繁测试）

1. **创建登录场景**
   - 场景名称：\"登录测试\"
   - 登录配置：执行登录
   - 勾选：保存会话

2. **设置为全局会话**
   - 在全局配置中设置
   - 或在场景管理中标记为全局

3. **其他场景使用全局会话**
   - 创建新场景
   - 登录配置：使用全局会话
   - 执行时自动跳过登录

### 方案 B：场景级会话

1. **创建登录场景**
   - 场景名称：\"登录测试\"
   - 登录配置：执行登录
   - 勾选：保存会话

2. **其他场景引用会话**
   - 创建新场景
   - 登录配置：使用指定会话
   - 选择：\"登录测试\"场景的会话

3. **执行测试**
   - 自动恢复会话
   - 跳过登录步骤

### 方案 C：每次登录

1. **创建场景**
   - 登录配置：执行登录
   - 不保存会话

2. **执行测试**
   - 每次都执行完整登录流程

## 优势

- 🚀 **提高效率** - 避免重复登录
- 💰 **降低成本** - 减少 LLM 调用
- ⏱️ **节省时间** - 测试速度更快
- 🔒 **灵活管理** - 支持多种登录方式
- 📊 **会话追踪** - 记录会话使用情况

## 注意事项

1. **会话过期**
   - 默认 24 小时后过期
   - 过期后需要重新登录

2. **会话冲突**
   - 不同环境使用不同会话
   - 建议按环境/用户分组

3. **安全性**
   - Cookies 包含敏感信息
   - 建议加密存储
   - 定期清理过期会话

## 下一步实现

还需要完成：

1. ✅ 数据模型 - 已完成
2. ✅ 会话管理服务 - 已完成
3. ⏳ 会话管理 API - 待实现
4. ⏳ 前端会话管理页面 - 待实现
5. ⏳ 测试执行流程优化 - 待实现
6. ⏳ 全局配置集成 - 待实现

## API 接口设计

`
POST /api/sessions - 创建会话
GET /api/sessions - 获取会话列表
GET /api/sessions/{id} - 获取会话详情
PUT /api/sessions/{id} - 更新会话
DELETE /api/sessions/{id} - 删除会话
POST /api/sessions/{id}/use - 使用会话
GET /api/sessions/global - 获取全局会话
PUT /api/sessions/global - 设置全局会话
`

## 前端页面设计

1. **会话管理页面**
   - 会话列表
   - 创建/编辑/删除会话
   - 设置全局会话
   - 查看会话详情

2. **场景创建/编辑页面**
   - 登录配置选择
   - 会话选择（如果选择使用会话）
   - 保存会话选项

## 数据库更新

需要运行数据库迁移以添加新表和字段：

`sql
-- 创建会话表
CREATE TABLE test_sessions (...);

-- 更新场景表
ALTER TABLE test_scenarios 
ADD COLUMN login_config VARCHAR(50) DEFAULT 'no_login',
ADD COLUMN session_id INT,
ADD COLUMN save_session BOOLEAN DEFAULT FALSE;
`

## 总结

这个方案提供了灵活的会话管理机制，可以根据实际需求选择：
- **全局会话** - 适用于单一环境的频繁测试
- **场景级会话** - 适用于多环境、多用户场景
- **每次登录** - 适用于需要确保最新状态的场景

通过会话复用，可以显著提高测试效率，降低成本！
