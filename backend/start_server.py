import asyncio
import sys
import uvicorn

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
        reload=False,  # 不要使用 reload，避免事件循环策略被重置
        access_log=True,
        log_level="debug",
        use_colors=True
    )