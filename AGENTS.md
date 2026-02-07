# E2E Testing Agent 项目说明

## 项目概述

这是一个智能 E2E（端到端）测试代理项目，使用自然语言指令自动化生成和执行 Web 应用的端到端测试。该项目基于 LangGraph 实现工作流编排，结合 Playwright 进行浏览器自动化，使用 LLM（Azure OpenAI）将用户测试需求转换为可执行的测试脚本。

### 核心技术栈

- **LangGraph** - 基于 LangChain 的图工作流编排框架，用于管理测试生成的多步骤流程
- **Playwright** - Python 版本的浏览器自动化工具，用于执行 E2E 测试
- **LangChain** - LLM 应用开发框架，用于与 Azure OpenAI 模型交互
- **Azure OpenAI** - 提供大语言模型能力，用于解析指令、生成代码和断言
- **Flask** - 提供测试用的示例 Web 应用
- **pytest-playwright** - Playwright 的 pytest 插件，用于测试执行
- **ipytest** - 在 Jupyter Notebook 中运行 pytest

### 项目架构

项目采用 LangGraph 工作流模式，通过多个节点协调完成测试生成：

1. **指令解析节点** - 将用户的自然语言测试需求转换为结构化的原子操作列表
2. **初始化节点** - 生成初始的 Playwright 脚本框架，包含页面导航
3. **状态获取节点** - 执行当前脚本并获取网页 DOM 状态
4. **代码生成节点** - 基于当前 DOM 状态和操作描述生成 Playwright 代码
5. **代码验证节点** - 验证生成的代码语法和完整性
6. **后处理节点** - 将完整的 Playwright 代码包装为 pytest 测试函数
7. **测试执行节点** - 使用 pytest 执行生成的测试
8. **报告生成节点** - 生成测试结果报告

## 构建和运行

### 环境要求

- Python 3.11+
- Azure OpenAI 账户和 API 密钥
- `.env` 文件配置 Azure OpenAI 相关环境变量

### 安装依赖

```bash
pip install langchain==0.2.16 langchain-community==0.2.16 langchain-core==0.2.38 langchain-experimental==0.0.65 langchain-openai==0.1.23 langchain-text-splitters==0.2.4 langgraph==0.2.18 langgraph-checkpoint==1.0.9 python-dotenv==1.0.1 openai==1.43.0 Flask==3.0.3 pytest-playwright==0.5.2 ipytest==0.14.2 nest-asyncio==1.6.0
```

### 运行项目

项目以 Jupyter Notebook 形式提供，主要执行流程：

1. 启动 Flask 测试应用（作为测试目标）：
```python
import subprocess
process = subprocess.Popen(
    ["flask", "run"],
    env={"FLASK_APP": "../data/e2e_testing_agent_app.py", "FLASK_ENV": "development", **os.environ}
)
```

2. 运行工作流生成并执行测试：
```python
query = "Test a registration form that contains username, password and password confirmation fields. After submitting it, verify that registration was successful."
target_url = "http://localhost:5000"
result = await run_workflow(query, target_url)
```

3. 查看测试报告：
```python
print(result["report"])
```

4. 测试完成后终止 Flask 进程：
```python
process.kill()
```

### Windows 系统注意事项

在 Windows 上的 Jupyter Notebook 中运行 Playwright 需要特殊处理。参考：https://github.com/microsoft/playwright-python/issues/178#issuecomment-1302869947

## 开发约定

### 代码结构

- **数据结构**：使用 `TypedDict` 定义 `GraphState` 管理工作流状态，使用 Pydantic `BaseModel` 定义结构化输出
- **异步编程**：所有工作流节点函数均为 `async` 函数，使用 `await` 处理异步操作
- **代码生成**：生成的 Playwright 代码必须：
  - 是原子性的，可独立执行
  - 使用 `await` 调用 Playwright API
  - 优先使用 `data-testid` 属性作为选择器
  - 最后一个操作必须包含断言验证

### 测试约定

- 生成的测试必须以 pytest 格式封装
- 使用 `@pytest.mark.asyncio` 装饰器标记异步测试
- 测试函数名由 LLM 根据用户需求自动生成
- 测试执行结果通过 `ipytest` 捕获输出

### 错误处理

- 代码生成错误时，提供详细的错误报告，包括错误信息、已尝试的操作和部分生成的脚本
- 使用 AST 解析验证生成的 Python 代码语法
- 检查生成的代码是否包含有效的 Playwright `page` 命令

### 选择器策略

1. 优先使用 `data-testid` 属性
2. 如果不存在，使用其他 CSS 选择器
3. 选择器定位基于当前 DOM 状态动态生成

## 关键文件

- `e2e_testing_agent.ipynb` - 主项目文件，包含完整的工作流定义、节点函数和执行示例
- `AGENTS.md` - 本文件，项目说明文档

## 使用场景

本项目适用于：
- 快速生成 E2E 测试用例
- 自动化回归测试
- 基于自然语言的测试需求转换
- 动态适应页面变化的测试脚本生成

## 局限性

- 需要稳定的网络连接访问 Azure OpenAI
- 复杂的动态页面可能需要多次迭代生成
- Windows 环境需要特殊配置
- 依赖 LLM 的代码质量，可能需要人工审查