import asyncio
import sys
import logging
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from typing import List, Optional

from ..core.database import get_db
from ..models.test_case import TestScenario, TestCase, TestReport, TestStepResult
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
    TestStepResultResponse,
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


@router.post("/{scenario_id}/generate", response_model=TestScenarioWithCases)
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

    try:
        # 先删除该场景下所有测试用例关联的测试报告
        print(f"   Deleting existing test reports for scenario {scenario_id}")
        # 获取该场景下所有测试用例的ID
        result = await db.execute(
            select(TestCase.id).where(TestCase.scenario_id == scenario_id)
        )
        test_case_ids = [row[0] for row in result.fetchall()]
        
        if test_case_ids:
            # 删除关联的测试报告
            await db.execute(
                delete(TestReport).where(TestReport.test_case_id.in_(test_case_ids))
            )
            await db.commit()
            print(f"   Deleted {len(test_case_ids)} test reports")
        
        # 删除该场景下所有现有的测试用例
        print(f"   Deleting existing test cases for scenario {scenario_id}")
        await db.execute(
            delete(TestCase).where(TestCase.scenario_id == scenario_id)
        )
        await db.commit()
        print(f"   Existing test cases deleted")

        # 获取场景的load_saved_storage配置
        load_saved_storage = scenario.load_saved_storage if hasattr(scenario, 'load_saved_storage') else True
        print(f"   Load saved storage from scenario: {load_saved_storage}")
        
        # 生成多个测试用例（内部会获取页面内容，并返回页面内容供后续使用）
        strategy = generation_strategy or scenario.generation_strategy
        test_cases_data, page_content = await test_generator.generate_multiple_test_cases(
            scenario.user_query,
            scenario.target_url,
            strategy,
            load_saved_storage
        )
        print(f"   Page content fetched: {page_content.get('title', 'N/A')}")

        # 为每个用例生成操作步骤和脚本
        generated_cases = []
        print(f"   开始处理 {len(test_cases_data)} 个测试用例数据...")
        for idx, case_data in enumerate(test_cases_data, 1):
            print(f"   处理第 {idx}/{len(test_cases_data)} 个用例: {case_data.get('name', 'Unknown')}")
            # 生成操作步骤
            actions = await test_generator.generate_actions(
                case_data["user_query"],
                scenario.target_url
            )

            # 生成测试脚本（使用已获取的页面内容，避免重复打开浏览器）
            print(f"   Generating script for test case: {case_data['name']}")
            # 从场景配置读取是否使用验证码和自动 Cookie/LocalStorage
            use_captcha = scenario.use_captcha if hasattr(scenario, 'use_captcha') else False
            auto_cookie_localstorage = scenario.auto_cookie_localstorage if hasattr(scenario, 'auto_cookie_localstorage') else True
            print(f"   Use captcha from scenario: {use_captcha}")
            print(f"   Auto cookie/localstorage from scenario: {auto_cookie_localstorage}")

            # 从全局配置读取是否使用 Computer-Use 方案
            use_computer_use_config = await db.execute(
                select(GlobalConfig).where(GlobalConfig.config_key == ConfigKeys.USE_COMPUTER_USE)
            )
            use_computer_use = False  # 默认不使用
            config_cu = use_computer_use_config.scalar_one_or_none()
            if config_cu and config_cu.config_value:
                use_computer_use = config_cu.config_value.lower() == "true"
            print(f"   Use Computer-Use from config: {use_computer_use}")

            # 根据配置选择使用哪种方案
            if use_computer_use:
                print(f"   Using Computer-Use approach for: {case_data['name']}")
                script_result = await test_executor.generate_script_with_computer_use(
                    case_data["user_query"],
                    scenario.target_url,
                    auto_detect_captcha=use_captcha,
                    auto_cookie_localstorage=auto_cookie_localstorage,
                    load_saved_storage=load_saved_storage,
                    page_content=page_content
                )
            else:
                print(f"   Using HTML approach for: {case_data['name']}")
                script_result = await test_executor.generate_script_only(
                    case_data["user_query"],
                    scenario.target_url,
                    auto_detect_captcha=use_captcha,
                    auto_cookie_localstorage=auto_cookie_localstorage,
                    load_saved_storage=load_saved_storage,
                    page_content=page_content
                )
            
            # 检查脚本生成是否成功
            if script_result.get("status") != "success":
                print(f"   ❌ 脚本生成失败: {script_result.get('error', 'Unknown error')}")
                continue  # 跳过这个测试用例
            
            script = script_result.get("script", "")
            print(f"   Script generated: {len(script)} chars")

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
                script=script,  # Save generated script
                priority=case_data.get("priority", "P1"),
                case_type=case_data.get("case_type", "positive"),
                status="generated"  # Generated but not executed
            )
            db.add(db_case)
            generated_cases.append(db_case)

        # 提交所有测试用例
        await db.commit()

        # 获取该场景下的所有测试用例
        cases_result = await db.execute(
            select(TestCase)
            .where(TestCase.scenario_id == scenario_id)
            .order_by(TestCase.priority, TestCase.created_at)
        )
        test_cases = cases_result.scalars().all()

        # 更新场景的total_cases
        await db.execute(
            update(TestScenario)
            .where(TestScenario.id == scenario_id)
            .values(total_cases=len(test_cases), status="generated")
        )
        await db.commit()

        # 返回完整的场景数据
        return TestScenarioWithCases(
            id=scenario.id,
            name=scenario.name,
            description=scenario.description,
            target_url=scenario.target_url,
            user_query=scenario.user_query,
            generation_strategy=scenario.generation_strategy,
            total_cases=len(test_cases),
            status="generated",
            created_at=scenario.created_at,
            updated_at=scenario.updated_at,
            use_captcha=scenario.use_captcha,
            auto_cookie_localstorage=scenario.auto_cookie_localstorage,
            load_saved_storage=scenario.load_saved_storage,
            test_cases=test_cases
        )

    except Exception as e:
        # 回滚当前事务
        await db.rollback()
        
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

    # 获取场景的load_saved_storage配置
    load_saved_storage = scenario.load_saved_storage if hasattr(scenario, 'load_saved_storage') else True
    print(f"   Load saved storage from scenario: {load_saved_storage}")
    
    for test_case in test_cases:
        try:
            # 更新用例状态
            await db.execute(
                update(TestCase)
                .where(TestCase.id == test_case.id)
                .values(status="executing")
            )
            await db.commit()

            # 优先使用已保存的脚本，但如果load_saved_storage为False，需要重新生成脚本
            if test_case.script and test_case.script.strip() and load_saved_storage:
                print(f"   Using saved script for test case {test_case.id}")
                execution_result = await test_executor.execute_saved_script(test_case.script)
            else:
                if not load_saved_storage:
                    print(f"   Regenerating script without loading saved storage for test case {test_case.id}")
                else:
                    print(f"   No saved script found, generating new script for test case {test_case.id}")
                
                # 从场景配置读取是否使用验证码和自动 Cookie/LocalStorage
                use_captcha = scenario.use_captcha if hasattr(scenario, 'use_captcha') else False
                auto_cookie_localstorage = scenario.auto_cookie_localstorage if hasattr(scenario, 'auto_cookie_localstorage') else True
                
                # 重新生成脚本，传入load_saved_storage配置
                script_result = await test_executor.generate_script_only(
                    test_case.user_query,
                    test_case.target_url,
                    auto_detect_captcha=use_captcha,
                    auto_cookie_localstorage=auto_cookie_localstorage,
                    load_saved_storage=load_saved_storage
                )
                
                if script_result.get("status") == "success":
                    # 执行生成的脚本
                    execution_result = await test_executor.execute_saved_script(script_result.get("script", ""))
                    # 更新测试用例的脚本
                    test_case.script = script_result.get("script", "")
                else:
                    execution_result = {
                        "status": "error",
                        "error": script_result.get("error", "Failed to generate script")
                    }

            # 更新用例
            status = "completed" if execution_result.get("status") == "success" else "failed"
            await db.execute(
                update(TestCase)
                .where(TestCase.id == test_case.id)
                .values(
                    script=execution_result.get("script") or test_case.script,
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
        .options(selectinload(TestReport.test_case))
        .where(TestReport.scenario_id == scenario_id)
        .order_by(TestReport.created_at.desc())
    )
    return result.scalars().all()

@router.get("/{scenario_id}/reports/{report_id}/steps", response_model=List[TestStepResultResponse])
async def get_scenario_report_steps(
    scenario_id: int,
    report_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取场景报告的步骤执行详情"""
    # 验证报告是否属于该场景
    report_result = await db.execute(
        select(TestReport)
        .where(TestReport.id == report_id)
        .where(TestReport.scenario_id == scenario_id)
    )
    report = report_result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    # 获取步骤结果
    steps_result = await db.execute(
        select(TestStepResult)
        .where(TestStepResult.test_report_id == report_id)
        .order_by(TestStepResult.step_number.asc())
    )
    steps = steps_result.scalars().all()
    return steps


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

            # 生成测试脚本（根据配置选择方案）
            if request.use_computer_use:
                # 使用 Computer-Use 方案（截图+坐标定位）
                execution_result = await test_executor.generate_script_with_computer_use(
                    case_data["user_query"],
                    target_url,
                    auto_detect_captcha=request.auto_detect_captcha
                )
            elif request.auto_detect_captcha:
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
