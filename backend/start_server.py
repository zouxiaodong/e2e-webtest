import asyncio
import sys
import os
import uvicorn

# 设置工作目录为backend目录
backend_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(backend_dir)
print(f"📁 工作目录设置为: {backend_dir}")

# 在 uvicorn 启动之前设置事件循环策略
if sys.platform == 'win32':
    print("🔄 设置 WindowsSelectorEventLoopPolicy 以支持 Playwright")
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print(f"✅ 当前事件循环策略: {asyncio.get_event_loop_policy().__class__.__name__}")

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Starting FastAPI server...")
    print("=" * 60)

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 使用 reload 模式，方便开发调试
        access_log=True,
        log_level="debug",
        use_colors=True
    )