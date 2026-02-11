from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from typing import List, Optional

from ..core.database import get_db
from ..models.test_case import TestCase, TestReport, TestStepResult
from ..schemas.test_case import (
    TestCaseCreate,
    TestCaseUpdate,
    TestCaseResponse,
    TestCaseGenerateRequest,
    TestCaseExecuteRequest,
    TestReportResponse,
    TestStepResultResponse
)
from ..services.executor.test_executor import test_executor
from ..services.generator.test_generator import test_generator

router = APIRouter(prefix="/api/test-cases", tags=["测试用例"])


@router.post("/", response_model=TestCaseResponse)
async def create_test_case(
    test_case: TestCaseCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建测试用例"""
    db_test_case = TestCase(**test_case.dict())
    db.add(db_test_case)
    await db.commit()
    await db.refresh(db_test_case)
    return db_test_case


@router.get("/", response_model=List[TestCaseResponse])
async def list_test_cases(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """获取测试用例列表"""
    result = await db.execute(
        select(TestCase)
        .offset(skip)
        .limit(limit)
        .order_by(TestCase.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{test_case_id}", response_model=TestCaseResponse)
async def get_test_case(
    test_case_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取测试用例详情"""
    result = await db.execute(
        select(TestCase).where(TestCase.id == test_case_id)
    )
    test_case = result.scalar_one_or_none()

    if not test_case:
        raise HTTPException(status_code=404, detail="测试用例不存在")

    return test_case


@router.put("/{test_case_id}", response_model=TestCaseResponse)
async def update_test_case(
    test_case_id: int,
    test_case_update: TestCaseUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新测试用例"""
    result = await db.execute(
        select(TestCase).where(TestCase.id == test_case_id)
    )
    test_case = result.scalar_one_or_none()

    if not test_case:
        raise HTTPException(status_code=404, detail="测试用例不存在")

    update_data = test_case_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(test_case, field, value)

    await db.commit()
    await db.refresh(test_case)
    return test_case


@router.delete("/{test_case_id}")
async def delete_test_case(
    test_case_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除测试用例"""
    result = await db.execute(
        select(TestCase).where(TestCase.id == test_case_id)
    )
    test_case = result.scalar_one_or_none()

    if not test_case:
        raise HTTPException(status_code=404, detail="测试用例不存在")

    await db.delete(test_case)
    await db.commit()
    return {"message": "测试用例已删除"}


@router.post("/{test_case_id}/generate")
async def generate_test_case(
    test_case_id: int,
    db: AsyncSession = Depends(get_db)
):
    """生成测试用例"""
    result = await db.execute(
        select(TestCase).where(TestCase.id == test_case_id)
    )
    test_case = result.scalar_one_or_none()

    if not test_case:
        raise HTTPException(status_code=404, detail="测试用例不存在")

    # 生成操作步骤
    actions = await test_generator.generate_actions(
        test_case.user_query,
        test_case.target_url
    )

    # 更新测试用例
    await db.execute(
        update(TestCase)
        .where(TestCase.id == test_case_id)
        .values(
            actions=actions,
            status="generated"
        )
    )
    await db.commit()

    return {
        "message": "测试用例生成成功",
        "actions": actions
    }


@router.post("/{test_case_id}/execute")
async def execute_test_case(
    test_case_id: int,
    db: AsyncSession = Depends(get_db)
):
    """执行测试用例"""
    result = await db.execute(
        select(TestCase).where(TestCase.id == test_case_id)
    )
    test_case = result.scalar_one_or_none()

    if not test_case:
        raise HTTPException(status_code=404, detail="测试用例不存在")

    # 更新状态为执行中
    await db.execute(
        update(TestCase)
        .where(TestCase.id == test_case_id)
        .values(status="executing")
    )
    await db.commit()

    try:
        # 执行测试
        execution_result = await test_executor.execute_workflow(
            test_case.user_query,
            test_case.target_url
        )

        # 更新测试用例
        await db.execute(
            update(TestCase)
            .where(TestCase.id == test_case_id)
            .values(
                script=execution_result.get("script"),
                status="completed" if execution_result.get("status") == "success" else "failed"
            )
        )

        # 创建测试报告
        test_report = TestReport(
            test_case_id=test_case_id,
            status="passed" if execution_result.get("status") == "success" else "failed",
            result=execution_result.get("report"),
            error_message=execution_result.get("error")
        )
        db.add(test_report)
        await db.commit()
        await db.refresh(test_report)  # 刷新以获取 ID
        
        # 保存步骤执行结果
        step_results = execution_result.get("step_results", [])
        for step_data in step_results:
            if step_data.get("event") == "step_start":
                # 创建步骤结果记录
                test_step = TestStepResult(
                    test_report_id=test_report.id,
                    step_number=step_data.get("step_number"),
                    step_name=step_data.get("step_name"),
                    step_type=step_data.get("step_type", "action"),
                    status="running",
                    start_time=datetime.fromisoformat(step_data.get("start_time")) if step_data.get("start_time") else None,
                    log_output=json.dumps(step_data, ensure_ascii=False)
                )
                db.add(test_step)
                await db.commit()  # 立即提交，确保 step_end 能找到
            elif step_data.get("event") == "step_end":
                # 更新步骤结果记录
                step_number = step_data.get("step_number")
                # 查找对应的 step_start 记录
                existing_step = await db.execute(
                    select(TestStepResult)
                    .where(TestStepResult.test_report_id == test_report.id)
                    .where(TestStepResult.step_number == step_number)
                    .where(TestStepResult.status == "running")
                    .order_by(TestStepResult.created_at.desc())
                )
                step = existing_step.scalar_one_or_none()
                
                if step:
                    # 更新现有记录
                    step.status = step_data.get("status", "passed")
                    step.end_time = datetime.fromisoformat(step_data.get("end_time")) if step_data.get("end_time") else None
                    step.execution_duration = step_data.get("execution_duration_ms")
                    step.output_data = step_data.get("output_data")
                    step.error_message = step_data.get("error_message")
                else:
                    # 创建新记录（如果没有对应的 step_start）
                    test_step = TestStepResult(
                        test_report_id=test_report.id,
                        step_number=step_number,
                        step_name="",  # 从 step_start 获取
                        step_type="action",
                        status=step_data.get("status", "passed"),
                        end_time=datetime.fromisoformat(step_data.get("end_time")) if step_data.get("end_time") else None,
                        execution_duration=step_data.get("execution_duration_ms"),
                        output_data=step_data.get("output_data"),
                        error_message=step_data.get("error_message"),
                        log_output=json.dumps(step_data, ensure_ascii=False)
                    )
                    db.add(test_step)
        
        await db.commit()

        return execution_result

    except Exception as e:
        # 更新状态为失败
        await db.execute(
            update(TestCase)
            .where(TestCase.id == test_case_id)
            .values(status="failed")
        )
        await db.commit()

        raise HTTPException(status_code=500, detail=f"测试执行失败: {str(e)}")


@router.get("/{test_case_id}/reports", response_model=List[TestReportResponse])
async def get_test_case_reports(
    test_case_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取测试用例的报告列表"""
    result = await db.execute(
        select(TestReport)
        .options(selectinload(TestReport.test_case))
        .where(TestReport.test_case_id == test_case_id)
        .order_by(TestReport.created_at.desc())
    )
    reports = result.scalars().all()
    return reports


@router.get("/{test_case_id}/reports/{report_id}/steps", response_model=List[TestStepResultResponse])
async def get_test_report_steps(
    test_case_id: int,
    report_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取测试报告的步骤执行详情"""
    # 验证报告是否属于该测试用例
    report_result = await db.execute(
        select(TestReport)
        .where(TestReport.id == report_id)
        .where(TestReport.test_case_id == test_case_id)
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
async def quick_generate_test_case(
    user_query: str,
    target_url: str
):
    """快速生成测试用例（不保存到数据库）"""
    try:
        result = await test_executor.execute_workflow(user_query, target_url)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@router.post("/quick-generate-with-captcha")
async def quick_generate_with_captcha(
    user_query: str,
    target_url: str,
    captcha_selector: str = None,
    captcha_input_selector: str = None
):
    """快速生成带验证码的测试用例"""
    try:
        result = await test_executor.execute_with_captcha(
            user_query,
            target_url,
            captcha_selector,
            captcha_input_selector
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")