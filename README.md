# AI 驱动的端到端测试平台

一个基于人工智能的自动化测试平台，使用自然语言描述测试需求，自动生成和执行端到端测试。

## 功能特性

- ✨ **一句话生成测试** - 使用自然语言描述测试需求，AI 自动生成测试用例
- 🔍 **智能验证码识别** - 基于百练平台视觉大模型（qwen-vl-plus），自动识别和处理验证码
- 🎭 **浏览器自动化** - 使用 Playwright 进行真实的浏览器操作模拟
- 📊 **自动生成报告** - 执行测试后自动生成详细的测试报告
- 🎨 **美观的 Web 界面** - 基于 Vue3 + Element Plus 的现代化管理界面
- 📝 **用例管理** - 完整的测试用例 CRUD 功能

## 技术栈

### 后端
- **FastAPI** - 现代化的 Python Web 框架
- **LangChain** - LLM 应用开发框架
- **LangGraph** - 图工作流编排
- **Playwright** - 浏览器自动化
- **SQLAlchemy** - ORM 框架
- **PostgreSQL** - 关系型数据库

### 前端
- **Vue 3** - 渐进式 JavaScript 框架
- **Element Plus** - Vue 3 组件库
- **Vite** - 下一代前端构建工具
- **Axios** - HTTP 客户端

### AI 服务
- **百练平台** - 通义千问大模型
- **qwen-plus** - 文本生成模型
- **qwen-vl-plus** - 视觉识别模型（验证码识别）

## 项目结构

```
e2etest/
├── backend/                 # 后端项目
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据库模型
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # 业务逻辑
│   │   │   ├── llm/        # 百练平台集成
│   │   │   ├── captcha/    # 验证码识别
│   │   │   ├── generator/  # 测试用例生成
│   │   │   └── executor/   # 测试执行
│   │   └── main.py         # FastAPI 应用入口
│   ├── requirements.txt    # Python 依赖
│   └── .env               # 环境配置
├── frontend/               # 前端项目
│   ├── src/
│   │   ├── api/           # API 调用
│   │   ├── components/    # 组件
│   │   ├── views/         # 页面
│   │   ├── router/        # 路由配置
│   │   ├── App.vue        # 根组件
│   │   └── main.js        # 入口文件
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 13+

### 1. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

编辑 `backend/.env` 文件：

```env
# 百练平台配置
BAILIAN_API_KEY=your_api_key_here
BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
BAILIAN_LLM_MODEL=qwen-plus
BAILIAN_VL_MODEL=qwen-vl-plus

# 数据库配置
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/e2e_test_db

# 应用配置
APP_NAME=AI-Driven E2E Testing Platform
APP_VERSION=1.0.0
DEBUG=True

# CORS 配置
CORS_ORIGINS=http://localhost:5173,http://localhost:5174

# 浏览器配置
BROWSER_HEADLESS=True
BROWSER_TIMEOUT=30000
```

### 3. 初始化数据库

```bash
# 创建 PostgreSQL 数据库
createdb e2e_test_db

# 数据库表会在应用启动时自动创建
```

### 4. 安装 Playwright 浏览器

```bash
playwright install chromium
```

### 5. 启动后端服务

```bash
cd backend
python -m app.main
```

后端服务将在 `http://localhost:8000` 启动

API 文档：`http://localhost:8000/docs`

### 6. 安装前端依赖

```bash
cd frontend
npm install
```

### 7. 启动前端服务

```bash
npm run dev
```

前端服务将在 `http://localhost:5173` 启动

## 使用指南

### 1. 快速生成测试用例

1. 访问 `http://localhost:5173`
2. 点击"快速生成"菜单
3. 填写目标 URL 和测试需求
4. 如果目标网站有验证码，启用验证码处理并填写选择器
5. 点击"生成测试用例"按钮
6. 等待 AI 生成测试用例和执行报告

### 2. 管理测试用例

1. 点击"测试用例"菜单
2. 点击"新建测试用例"创建新用例
3. 点击"生成"按钮生成测试脚本
4. 点击"执行"按钮运行测试
5. 点击"查看"查看详细信息和报告

### 3. 验证码处理

平台支持自动处理验证码：

- **验证码选择器**：验证码图片元素的 CSS 选择器，例如 `#captcha img`
- **输入框选择器**：验证码输入框的 CSS 选择器，例如 `#captcha-input`

系统会自动截取验证码图片，使用 qwen-vl-plus 模型识别内容，并填入输入框。

## API 文档

启动后端服务后，访问 `http://localhost:8000/docs` 查看完整的 API 文档。

### 主要 API 端点

- `POST /api/test-cases/quick-generate` - 快速生成测试用例
- `POST /api/test-cases/quick-generate-with-captcha` - 快速生成带验证码的测试用例
- `GET /api/test-cases` - 获取测试用例列表
- `POST /api/test-cases` - 创建测试用例
- `POST /api/test-cases/{id}/generate` - 生成测试脚本
- `POST /api/test-cases/{id}/execute` - 执行测试

## 工作原理

### 测试生成流程

1. **指令解析** - 将用户的自然语言查询转换为结构化的操作步骤
2. **代码生成** - 为每个操作步骤生成 Playwright 代码
3. **DOM 分析** - 执行代码获取当前页面状态
4. **迭代生成** - 基于页面状态生成下一个操作的代码
5. **测试执行** - 运行完整的测试脚本
6. **报告生成** - 生成详细的测试报告

### 验证码处理流程

1. 截取验证码元素图片
2. 将图片转换为 base64 编码
3. 调用 qwen-vl-plus 模型识别验证码内容
4. 将识别结果填入输入框

## 注意事项

1. **Windows 系统特殊处理**
   - 在 Windows 上运行 Playwright 可能需要特殊配置
   - 参考：https://github.com/microsoft/playwright-python/issues/178#issuecomment-1302869947

2. **验证码识别**
   - 验证码识别准确率取决于验证码的复杂程度
   - 简单的数字/字母验证码识别率较高
   - 复杂的滑动验证码可能需要其他方案

3. **API 调用限制**
   - 百练平台 API 有调用频率限制
   - 建议合理控制测试生成的频率

4. **浏览器资源**
   - 每个测试用例执行会启动新的浏览器实例
   - 测试完成后浏览器会自动关闭

## 常见问题

### Q: 如何获取百练平台 API Key？

A: 访问阿里云百练平台（https://bailian.console.aliyun.com/）注册并创建 API Key。

### Q: 数据库连接失败怎么办？

A: 检查 `backend/.env` 中的 `DATABASE_URL` 配置是否正确，确保 PostgreSQL 服务正在运行。

### Q: 前端无法连接后端怎么办？

A: 检查后端服务是否正常启动，查看 `frontend/vite.config.js` 中的代理配置。

### Q: 验证码识别失败怎么办？

A: 检查验证码选择器是否正确，确保验证码元素在页面中可见。

## 开发计划

- [ ] 支持更多浏览器（Firefox、Safari）
- [ ] 支持测试用例导入/导出
- [ ] 支持测试用例定时执行
- [ ] 支持测试结果对比和历史记录
- [ ] 支持多用户和权限管理
- [ ] 支持测试用例模板

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交 Issue。