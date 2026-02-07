# AI 驱动的端到端测试平台

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue-3.5-42b883.svg)](https://vuejs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 基于百练平台大模型和 Playwright 的智能 E2E 测试自动化平台

## 📖 项目简介

这是一个创新的端到端（E2E）测试自动化平台，利用百练平台的大模型能力，让用户通过自然语言描述测试需求，自动生成、执行测试用例，并提供详细的测试报告。

### 核心特性

- 🤖 **AI 驱动** - 使用百练平台通义千问模型自动生成测试用例
- 🎯 **一句话生成** - 用自然语言描述需求，AI 自动生成 1-N 个测试用例
- 🔄 **场景管理** - 支持测试场景与用例的层级管理
- 🔐 **智能验证码识别** - 使用 qwen-vl-plus 模型自动识别验证码
- 🌐 **Web 界面** - 现代化的 Vue3 + Element Plus 管理界面
- 💾 **会话复用** - 支持登录会话保存和复用，提高测试效率
- 📊 **详细报告** - 自动生成 Markdown 格式的测试报告
- ⚙️ **全局配置** - 统一管理 URL、用户名、密码等配置

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- MySQL 5.7+
- Playwright 浏览器

### 安装步骤

#### 1. 克隆项目

`ash
git clone <repository-url>
cd e2etest
`

#### 2. 配置环境变量

复制后端环境变量模板：

`ash
cd backend
cp .env.example .env
`

编辑 .env 文件，填入真实配置：

`env
# 百练平台配置
BAILIAN_API_KEY=your_api_key_here
BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
BAILIAN_LLM_MODEL=qwen-plus
BAILIAN_VL_MODEL=qwen-vl-plus

# 数据库配置
DATABASE_URL=mysql+aiomysql://username:password@host:port/database

# 其他配置...
`

#### 3. 安装后端依赖

`ash
cd backend
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
`

#### 4. 创建数据库

`ash
# 创建数据库
mysql -u root -p
CREATE DATABASE e2etest CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;
`

#### 5. 启动后端服务

`ash
cd backend
python -m app.main
`

后端服务将在 http://localhost:8000 启动

#### 6. 安装前端依赖

`ash
cd frontend
npm install
`

#### 7. 启动前端服务

`ash
npm run dev
`

前端服务将在 http://localhost:5174 启动

## 📚 使用指南

### 快速生成测试用例

1. 访问前端页面 http://localhost:5174
2. 点击"快速生成"菜单
3. 填写目标 URL 和测试需求
4. 选择生成策略：
   - 仅正向测试（1个用例）
   - 基础覆盖（3个用例）
   - 全面测试（5个用例）
5. 可选：开启"自动识别验证码"
6. 点击"生成测试用例"

### 使用全局配置

1. 访问"全局配置"页面
2. 设置默认 URL、用户名、密码等
3. 保存配置
4. 在快速生成时，开启"使用全局配置"

### 管理测试场景

1. 访问"测试场景"页面
2. 创建新场景，填写场景描述
3. 选择登录配置：
   - 不需要登录
   - 执行登录
   - 使用全局会话
   - 使用指定会话
4. 生成和执行测试用例

## 🏗️ 项目结构

`
e2etest/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── api/               # API 路由
│   │   │   ├── test_cases.py  # 测试用例 API
│   │   │   ├── scenarios.py   # 场景管理 API
│   │   │   ├── configs.py     # 全局配置 API
│   │   │   └── sessions.py    # 会话管理 API
│   │   ├── core/              # 核心配置
│   │   │   ├── config.py      # 配置管理
│   │   │   ├── database.py    # 数据库配置
│   │   │   └── llm_logger.py  # LLM 日志
│   │   ├── models/            # 数据模型
│   │   │   ├── test_case.py   # 场景和用例模型
│   │   │   ├── global_config.py # 全局配置模型
│   │   │   └── test_session.py # 会话模型
│   │   ├── schemas/           # Pydantic schemas
│   │   │   ├── test_case.py
│   │   │   ├── global_config.py
│   │   │   └── ...
│   │   ├── services/          # 业务逻辑
│   │   │   ├── llm/          # LLM 集成
│   │   │   │   └── bailian_client.py
│   │   │   ├── captcha/      # 验证码服务
│   │   │   ├── generator/    # 测试生成引擎
│   │   │   ├── executor/     # 测试执行引擎
│   │   │   └── session/      # 会话管理
│   │   └── main.py           # 应用入口
│   ├── logs/                  # 日志目录
│   ├── requirements.txt        # Python 依赖
│   └── .env                   # 环境变量（不提交）
├── frontend/                   # 前端应用
│   ├── src/
│   │   ├── api/               # API 调用
│   │   ├── components/        # 公共组件
│   │   ├── views/             # 页面组件
│   │   ├── router/            # 路由配置
│   │   ├── utils/             # 工具函数
│   │   ├── App.vue            # 根组件
│   │   └── main.js            # 入口文件
│   ├── package.json           # Node.js 依赖
│   └── vite.config.js         # Vite 配置
├── README.md                   # 项目文档
├── IMPROVEMENTS.md             # 改进说明
├── SESSION_MANAGEMENT.md       # 会话管理方案
└── LLM_LOGS.md                 # LLM 日志说明
`

## 🔧 配置说明

### 百练平台配置

在 ackend/.env 中配置：

`env
BAILIAN_API_KEY=your_api_key
BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
BAILIAN_LLM_MODEL=qwen-plus          # 文本生成模型
BAILIAN_VL_MODEL=qwen-vl-plus        # 视觉识别模型
`

### 数据库配置

`env
DATABASE_URL=mysql+aiomysql://username:password@host:port/database
`

**注意：** 密码中的特殊字符（如 @, #, !）需要进行 URL 编码：
- @ → %40
- # → %23
- ! → %21

示例：密码 E2e123!@# 编码为 E2e123!%40%23

### 浏览器配置

`env
BROWSER_HEADLESS=True          # 无头模式（关闭后可看到浏览器）
BROWSER_TIMEOUT=30000          # 超时时间（毫秒）
`

## 📖 更多文档

- [改进说明](IMPROVEMENTS.md) - 专业测试场景和用例改进
- [会话管理](SESSION_MANAGEMENT.md) - 登录会话复用方案
- [LLM 日志](backend/LLM_LOGS.md) - LLM 交互日志说明
- [API 文档](http://localhost:8000/docs) - Swagger API 文档

## 🤝 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork 本仓库
2. 创建特性分支 (git checkout -b feature/AmazingFeature)
3. 提交更改 (git commit -m 'Add some AmazingFeature')
4. 推送到分支 (git push origin feature/AmazingFeature)
5. 提交 Pull Request

## 📄 许可证

本项目采用 MIT 许可证。详情请参阅 [LICENSE](LICENSE) 文件。

## ❓ 常见问题

### Q: Playwright 在 Windows 上启动失败？

A: 请确保已安装 Playwright 浏览器：

`ash
playwright install chromium
`

如果仍有问题，请检查事件循环策略（代码中已处理）。

### Q: 如何查看 LLM 交互日志？

A: 日志文件位于 ackend/logs/llm_interactions.log，使用以下命令查看：

`ash
# 查看所有日志
cat backend/logs/llm_interactions.log

# 实时查看
tail -f backend/logs/llm_interactions.log
`

### Q: 验证码识别失败怎么办？

A: 检查以下几点：
1. 确保 qwen-vl-plus 模型配置正确
2. 检查验证码图片是否清晰可见
3. 查看后端日志了解详细错误信息

### Q: 如何提高测试效率？

A: 使用会话复用功能：
1. 创建登录场景并保存会话
2. 其他场景选择"使用全局会话"或"使用指定会话"
3. 自动跳过登录步骤

### Q: Token 使用量如何监控？

A: 查看后端日志文件，每次 LLM 调用都会记录：
- 估算的输入 tokens
- 估算的输出 tokens
- 实际的 token 使用情况（如果 API 返回）

## 📞 联系方式

如有问题或建议，请通过以下方式联系：

- 提交 Issue
- 发送邮件
- 加入讨论组

## 🙏 致谢

- [百练平台](https://www.aliyun.com/product/bailian) - 提供强大的大模型服务
- [Playwright](https://playwright.dev/) - 现代化的浏览器自动化工具
- [FastAPI](https://fastapi.tiangolo.com/) - 高性能的 Python Web 框架
- [Vue 3](https://vuejs.org/) - 渐进式 JavaScript 框架
- [Element Plus](https://element-plus.org/) - Vue 3 组件库

---

**Made with ❤️ using AI**
