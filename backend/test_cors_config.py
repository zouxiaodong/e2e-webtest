from app.core.config import settings

print("=" * 60)
print("CORS 配置检查")
print("=" * 60)
print(f"CORS_ORIGINS (原始字符串): {settings.CORS_ORIGINS}")
print(f"CORS_ORIGINS_LIST (解析后的列表): {settings.cors_origins_list}")
print("=" * 60)
print("检查是否包含前端 origin:")
print(f"  - http://localhost:5174: {'http://localhost:5174' in settings.cors_origins_list}")
print(f"  - http://127.0.0.1:5174: {'http://127.0.0.1:5174' in settings.cors_origins_list}")
print("=" * 60)