from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List

from ..core.database import get_db
from ..models.global_config import GlobalConfig, ConfigKeys
from ..schemas.global_config import (
    GlobalConfigCreate,
    GlobalConfigUpdate,
    GlobalConfigResponse,
    GlobalConfigSettings
)

router = APIRouter(prefix="/api/configs", tags=["全局配置"])


@router.get("/", response_model=List[GlobalConfigResponse])
async def list_configs(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """获取所有配置"""
    result = await db.execute(
        select(GlobalConfig)
        .offset(skip)
        .limit(limit)
        .order_by(GlobalConfig.config_key)
    )
    return result.scalars().all()


@router.get("/settings", response_model=GlobalConfigSettings)
async def get_settings(db: AsyncSession = Depends(get_db)):
    """获取全局配置设置"""
    # 获取所有配置
    result = await db.execute(select(GlobalConfig))
    configs = result.scalars().all()
    
    # 转换为字典
    config_dict = {c.config_key: c.config_value for c in configs}
    
    return GlobalConfigSettings(
        target_url=config_dict.get(ConfigKeys.TARGET_URL),
        default_username=config_dict.get(ConfigKeys.DEFAULT_USERNAME),
        default_password=config_dict.get(ConfigKeys.DEFAULT_PASSWORD),
        captcha_selector=config_dict.get(ConfigKeys.CAPTCHA_SELECTOR),
        captcha_input_selector=config_dict.get(ConfigKeys.CAPTCHA_INPUT_SELECTOR),
        browser_headless=config_dict.get(ConfigKeys.BROWSER_HEADLESS, "true") == "true",
        use_computer_use=config_dict.get(ConfigKeys.USE_COMPUTER_USE, "false") == "true",
        browser_timeout=int(config_dict.get(ConfigKeys.BROWSER_TIMEOUT, "30000"))
    )


@router.put("/settings")
async def update_settings(
    settings: GlobalConfigSettings,
    db: AsyncSession = Depends(get_db)
):
    """更新全局配置设置"""
    print(f"收到配置更新请求: {settings}")
    
    # 定义配置映射
    config_mappings = [
        (ConfigKeys.TARGET_URL, settings.target_url, "目标URL", "string"),
        (ConfigKeys.DEFAULT_USERNAME, settings.default_username, "默认用户名", "string"),
        (ConfigKeys.DEFAULT_PASSWORD, settings.default_password, "默认密码", "string"),
        (ConfigKeys.CAPTCHA_SELECTOR, settings.captcha_selector, "验证码选择器", "string"),
        (ConfigKeys.CAPTCHA_INPUT_SELECTOR, settings.captcha_input_selector, "验证码输入框选择器", "string"),
        (ConfigKeys.BROWSER_HEADLESS, str(settings.browser_headless).lower(), "浏览器无头模式", "boolean"),
        (ConfigKeys.USE_COMPUTER_USE, str(settings.use_computer_use).lower(), "使用Computer-Use方案", "boolean"),
        (ConfigKeys.BROWSER_TIMEOUT, str(settings.browser_timeout), "浏览器超时时间", "number"),
    ]
    
    updated_count = 0
    for key, value, description, config_type in config_mappings:
        print(f"处理配置: {key} = {value} (type: {type(value).__name__})")
        if value is not None:
            result = await db.execute(
                select(GlobalConfig).where(GlobalConfig.config_key == key)
            )
            config = result.scalar_one_or_none()
            
            if config:
                # 更新现有配置
                print(f"  更新现有配置: {key}")
                await db.execute(
                    update(GlobalConfig)
                    .where(GlobalConfig.config_key == key)
                    .values(config_value=value)
                )
            else:
                # 创建新配置
                print(f"  创建新配置: {key}")
                new_config = GlobalConfig(
                    config_key=key,
                    config_value=value,
                    config_type=config_type,
                    description=description
                )
                db.add(new_config)
            updated_count += 1
        else:
            print(f"  跳过配置（值为None）: {key}")
    
    await db.commit()
    print(f"配置更新完成，共更新 {updated_count} 项配置")
    return {"message": "配置更新成功"}


@router.get("/{config_key}", response_model=GlobalConfigResponse)
async def get_config(
    config_key: str,
    db: AsyncSession = Depends(get_db)
):
    """获取指定配置"""
    result = await db.execute(
        select(GlobalConfig).where(GlobalConfig.config_key == config_key)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    return config


@router.put("/{config_key}", response_model=GlobalConfigResponse)
async def update_config(
    config_key: str,
    config_update: GlobalConfigUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新指定配置"""
    result = await db.execute(
        select(GlobalConfig).where(GlobalConfig.config_key == config_key)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    update_data = config_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)
    
    await db.commit()
    await db.refresh(config)
    return config
