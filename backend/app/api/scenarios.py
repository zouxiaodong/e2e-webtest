import asyncio
import sys
import logging
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from typing import List, Optional

from ..core.database import get_db
from ..models.test_case import TestScenario, TestCase, TestReport
from ..models.global_config import GlobalConfig, ConfigKeys
from ..schemas.test_case import (
    TestScenarioCreate,
    TestScenarioUpdate,
    TestScenarioResponse,
    TestScenarioWithCases,
    ScenarioGenerateRequest,
    ScenarioExecuteRequest,
    QuickGenerateRequest,
    TestCaseResponse,
    TestReportResponse,
    GenerationStrategy
)
from ..services.executor.test_executor import test_executor
from ..services.generator.test_generator import test_generator

router = APIRouter(prefix="/api/scenarios", tags=["测试场景"])


@router.post("/", response_model=TestScenarioResponse)
async def create_scenario(
    scenario: TestScenarioCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建测试场景"""
    # 如果target_url为空，从数据库中获取TARGET_URL配置
    if not scenario.target_url:
        from ..models.global_config import GlobalConfig, ConfigKeys
        from sqlalchemy import select
        
        result = await db.execute(
            select(GlobalConfig).where(GlobalConfig.config_key == ConfigKeys.TARGET_URL)
        )
        config = result.scalar_one_or_none()
        if config:
            scenario.target_url = config.config_value
    
    db_scenario = TestScenario(**scenario.dict())
    db.add(db_scenario)
    await db.commit()
    await db.refresh(db_scenario)
    return db_scenario


@router.get("/", response_model=List[TestScenarioResponse])
async def list_scenarios(
    skip: int = 0,
    limit: int = 100,
    status: str = None,
    db: AsyncSession = Depends(get_db)
):
    """获取测试场景列表"""
    query = select(TestScenario)
    if status:
        query = query.where(TestScenario.status == status)

    query = query.offset(skip).limit(limit).order_by(TestScenario.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{scenario_id}", response_model=TestScenarioWithCases)
async def get_scenario(
    scenario_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取测试场景详情（包含用例）"""
    result = await db.execute(
        select(TestScenario).where(TestScenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()

    if not scenario:
        raise HTTPException(status_code=404, detail="测试场景不存在")

    # 获取该场景下的所有测试用例
    cases_result = await db.execute(
        select(TestCase)
        .where(TestCase.scenario_id == scenario_id)
        .order_by(TestCase.priority, TestCase.created_at)
    )
    test_cases = cases_result.scalars().all()

    # 转换为响应模型
    scenario_dict = {
        "id": scenario.id,
        "name": scenario.name,
        "description": scenario.description,
        "target_url": scenario.target_url,
        "user_query": scenario.user_query,
        "generation_strategy": scenario.generation_strategy,
        "total_cases": scenario.total_cases,
        "status": scenario.status,
        "created_at": scenario.created_at,
        "updated_at": scenario.updated_at,
        "test_cases": test_cases
    }

    return TestScenarioWithCases(**scenario_dict)


@router.put("/{scenario_id}", response_model=TestScenarioResponse)
async def update_scenario(
    scenario_id: int,
    scenario_update: TestScenarioUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新测试场景"""
    result = await db.execute(
        select(TestScenario).where(TestScenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()

    if not scenario:
        raise HTTPException(status_code=404, detail="测试场景不存在")

    update_data = scenario_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(scenario, field, value)

    await db.commit()
    await db.refresh(scenario)
    return scenario


@router.delete("/{scenario_id}")
async def delete_scenario(
    scenario_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除测试场景（级联删除所有用例）"""
    result = await db.execute(
        select(TestScenario).where(TestScenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()

    if not scenario:
        raise HTTPException(status_code=404, detail="测试场景不存在")

    await db.delete(scenario)
    await db.commit()
    return {"message": "测试场景已删除"}


@router.post("/{scenario_id}/generate")
async def generate_scenario_cases(
    scenario_id: int,
    generation_strategy: Optional[GenerationStrategy] = None,
    db: AsyncSession = Depends(get_db)
):
    """为场景生成测试用例"""
    result = await db.execute(
        select(TestScenario).where(TestScenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()

    if not scenario:
        raise HTTPException(status_code=404, detail="测试场景不存在")

    # 更新场景状态为 generating
    await db.execute(
        update(TestScenario)
        .where(TestScenario.id == scenario_id)
        .values(status="generating")
    )
    await db.commit()

    try:
        # 生成多个测试用例
        strategy = generation_strategy or scenario.generation_strategy
        test_cases_data = await test_generator.generate_multiple_test_cases(
            scenario.user_query,
            scenario.target_url,
            strategy
        )

        # 为每个用例生成操作步骤和脚本
        generated_cases = []
        for case_data in test_cases_data:
            # 生成操作步骤
            actions = await test_generator.generate_actions(
                case_data["user_query"],
                scenario.target_url
            )

            # 生成测试脚本
            # 创建测试用例
            # 将 expected_result 转换为 JSON 字符串
            expected_result = case_data.get("expected_result")
            if isinstance(expected_result, dict):
                expected_result = json.dumps(expected_result, ensure_ascii=False)
            
            db_case = TestCase(
                scenario_id=scenario.id,
                name=case_data["name"],
                description=case_data["description"],
                target_url=scenario.target_url,
                user_query=case_data["user_query"],
                test_data=case_data.get("test_data", {}),
                expected_result=expected_result,
                actions=actions,
                script="",  # Placeholder script
                priority=case_data.get("priority", "P1"),
                case_type=case_data.get("case_type", "positive"),
                status="generated"  # Generated but not executed
            )
            db.add(db_case)
            generated_cases.append(db_case)

        # 提交所有测试用例
        await db.commit()

        # 更新场景状态为 completed
        await db.execute(
            update(TestScenario)
            .where(TestScenario.id == scenario_id)
            .values(
                total_cases=len(generated_cases),
                status="completed"
            )
        )
        await db.commit()

        return {
            "message": f"成功生成 {len(generated_cases)} 个测试用例",
            "test_cases": generated_cases
        }

    except Exception as e:
        # 回滚当前事务
        await db.rollback()
        
        # 更新场景状态为失败
        try:
            await db.execute(
                update(TestScenario)
                .where(TestScenario.id == scenario_id)
                .values(status="failed")
            )
            await db.commit()
        except Exception as update_error:
            # 如果更新状态也失败，继续回滚
            await db.rollback()
            print(f"Failed to update scenario status: {update_error}")

        # 记录详细错误
        import traceback
        error_detail = traceback.format_exc()
        print(f"生成测试用例失败: {str(e)}")
        print(f"错误堆栈:\n{error_detail}")
        
        raise HTTPException(status_code=500, detail=f"生成测试用例失败: {str(e)}")


@router.post("/{scenario_id}/execute")
async def execute_scenario_cases(
    scenario_id: int,
    db: AsyncSession = Depends(get_db)
):
    """执行场景下的所有测试用例"""
    result = await db.execute(
        select(TestScenario).where(TestScenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()

    if not scenario:
        raise HTTPException(status_code=404, detail="测试场景不存在")

    # 获取该场景下的所有测试用例
    cases_result = await db.execute(
        select(TestCase)
        .where(TestCase.scenario_id == scenario_id)
        .order_by(TestCase.priority)
    )
    test_cases = cases_result.scalars().all()

    if not test_cases:
        raise HTTPException(status_code=400, detail="该场景下没有测试用例")

    # 执行所有用例
    execution_results = []
    passed_count = 0
    failed_count = 0

    for test_case in test_cases:
        try:
            # 更新用例状态
            await db.execute(
                update(TestCase)
                .where(TestCase.id == test_case.id)
                .values(status="executing")
            )
            await db.commit()

            # 执行测试
            execution_result = await test_executor.execute_workflow(
                test_case.user_query,
                test_case.target_url
            )

            # 更新用例
            status = "completed" if execution_result.get("status") == "success" else "failed"
            await db.execute(
                update(TestCase)
                .where(TestCase.id == test_case.id)
                .values(
                    script=execution_result.get("script"),
                    status=status,
                    execution_count=test_case.execution_count + 1
                )
            )

            # 创建测试报告
            test_report = TestReport(
                test_case_id=test_case.id,
                scenario_id=scenario.id,
                status="passed" if execution_result.get("status") == "success" else "failed",
                result=execution_result.get("report"),
                error_message=execution_result.get("error")
            )
            db.add(test_report)

            execution_results.append({
                "test_case_id": test_case.id,
                "test_case_name": test_case.name,
                "status": status,
                "result": execution_result.get("report")
            })

            if execution_result.get("status") == "success":
                passed_count += 1
            else:
                failed_count += 1

        except Exception as e:
            # 更新用例状态为失败
            await db.execute(
                update(TestCase)
                .where(TestCase.id == test_case.id)
                .values(status="failed")
            )
            await db.commit()

            execution_results.append({
                "test_case_id": test_case.id,
                "test_case_name": test_case.name,
                "status": "error",
                "error": str(e)
            })
            failed_count += 1

    await db.commit()

    return {
        "message": f"执行完成，通过 {passed_count} 个，失败 {failed_count} 个",
        "total": len(test_cases),
        "passed": passed_count,
        "failed": failed_count,
        "results": execution_results
    }


@router.get("/{scenario_id}/cases", response_model=List[TestCaseResponse])
async def get_scenario_cases(
    scenario_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取场景下的所有测试用例"""
    result = await db.execute(
        select(TestCase)
        .where(TestCase.scenario_id == scenario_id)
        .order_by(TestCase.priority, TestCase.created_at)
    )
    return result.scalars().all()


@router.get("/{scenario_id}/reports", response_model=List[TestReportResponse])
async def get_scenario_reports(
    scenario_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取场景下所有用例的报告"""
    result = await db.execute(
        select(TestReport)
        .where(TestReport.scenario_id == scenario_id)
        .order_by(TestReport.created_at.desc())
    )
    return result.scalars().all()


@router.post("/quick-generate")
async def quick_generate_scenario(
    request: QuickGenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """快速生成场景和测试用例（不保存到数据库）"""
    try:
        # 如果未提供目标URL，从全局配置中获取
        target_url = request.target_url
        if not target_url:
            from ..models.global_config import ConfigKeys
            from sqlalchemy import select
            
            result = await db.execute(
                select(GlobalConfig).where(GlobalConfig.config_key == ConfigKeys.TARGET_URL)
            )
            config = result.scalar_one_or_none()
            if config:
                target_url = config.config_value
        
        if not target_url:
            raise HTTPException(
                status_code=400, 
                detail="未提供目标URL，请在请求中提供或在全局配置中设置"
            )
        
        # 生成多个测试用例
        test_cases_data = await test_generator.generate_multiple_test_cases(
            request.user_query,
            target_url,
            request.generation_strategy
        )

        # 为每个用例生成操作步骤和脚本
        generated_cases = []
        for case_data in test_cases_data:
            # 生成操作步骤
            actions = await test_generator.generate_actions(
                case_data["user_query"],
                target_url
            )

            # 生成测试脚本（带验证码）
            if request.auto_detect_captcha:
                execution_result = await test_executor.execute_with_captcha(
                    case_data["user_query"],
                    target_url,
                    auto_detect=True
                )
            else:
                execution_result = await test_executor.execute_workflow(
                    case_data["user_query"],
                    target_url
                )

            generated_cases.append({
                "name": case_data["name"],
                "description": case_data["description"],
                "user_query": case_data["user_query"],
                "test_data": case_data.get("test_data", {}),
                "expected_result": case_data.get("expected_result"),
                "priority": case_data.get("priority", "P1"),
                "case_type": case_data.get("case_type", "positive"),
                "actions": actions,
                "script": execution_result.get("script"),
                "report": execution_result.get("report"),
                "status": execution_result.get("status")
            })

        return {
            "scenario": {
                "name": "快速生成场景",
                "description": request.user_query,
                "target_url": target_url,
                "generation_strategy": request.generation_strategy.value,
                "total_cases": len(generated_cases)
            },
            "test_cases": generated_cases,
            "summary": {
                "total": len(generated_cases),
                "passed": sum(1 for c in generated_cases if c.get("status") == "success"),
                "failed": sum(1 for c in generated_cases if c.get("status") != "success")
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")
