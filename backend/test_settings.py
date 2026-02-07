from app.core.config import settings

print("=" * 60)
print("Settings 检查")
print("=" * 60)
print(f"CORS_ORIGINS: {settings.CORS_ORIGINS}")
print(f"cors_origins_list: {settings.cors_origins_list}")
print(f"allow_all: {'*' in settings.cors_origins_list}")
print("=" * 60)