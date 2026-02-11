from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime
from enum import Enum


class GenerationStrategy(str, Enum):
    """生成策略"""
    HAPPY_PATH = "happy_path"  # 仅正向测试
    BASIC = "basic"  # 基础覆盖（正向+主要异常）
    COMPREHENSIVE = "comprehensive"  # 全面测试


class TestCasePriority(str, Enum):
    """测试用例优先级"""
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TestCaseType(str, Enum):
    """测试用例类型"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    BOUNDARY = "boundary"
    EXCEPTION = "exception"
    SECURITY = "security"
    PERFORMANCE = "performance"
    COMPATIBILITY = "compatibility"


# ==================== 场景相关 Schemas ====================

class TestScenarioBase(BaseModel):
    """测试场景基础模型"""
    name: str = Field(..., description="场景名称")
    description: Optional[str] = Field(None, description="场景描述")
    target_url: str = Field(..., description="目标URL")
    user_query: str = Field(..., description="用户自然语言描述的场景")
    generation_strategy: GenerationStrategy = Field(GenerationStrategy.BASIC, description="生成策略")
    use_captcha: bool = Field(False, description="是否使用验证码")
    auto_cookie_localstorage: bool = Field(True, description="自动加载和保存 cookie/localstorage")
    load_saved_storage: bool = Field(True, description="是否加载保存的 cookie/localstorage/sessionstorage")


class TestScenarioCreate(TestScenarioBase):
    """创建测试场景请求"""
    pass


class TestScenarioUpdate(BaseModel):
    """更新测试场景请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    target_url: Optional[str] = None
    user_query: Optional[str] = None
    generation_strategy: Optional[GenerationStrategy] = None
    status: Optional[str] = None
    use_captcha: Optional[bool] = None
    auto_cookie_localstorage: Optional[bool] = None
    load_saved_storage: Optional[bool] = None


class TestScenarioResponse(TestScenarioBase):
    """测试场景响应"""
    id: int
    total_cases: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TestScenarioWithCases(TestScenarioResponse):
    """包含用例的场景响应"""
    test_cases: List['TestCaseResponse'] = []


class ScenarioGenerateRequest(BaseModel):
    """生成场景测试用例请求"""
    scenario_id: int
    generation_strategy: Optional[GenerationStrategy] = None


class ScenarioExecuteRequest(BaseModel):
    """执行场景所有用例请求"""
    scenario_id: int


# ==================== 用例相关 Schemas ====================

class TestCaseBase(BaseModel):
    """测试用例基础模型"""
    name: str = Field(..., description="测试用例名称")
    description: Optional[str] = Field(None, description="测试用例描述")
    target_url: str = Field(..., description="目标URL")
    user_query: str = Field(..., description="用例的具体测试需求")
    test_data: Optional[Dict[str, Any]] = Field(None, description="测试数据")
    expected_result: Optional[str] = Field(None, description="预期结果")


class TestCaseCreate(TestCaseBase):
    """创建测试用例请求"""
    scenario_id: Optional[int] = Field(None, description="所属场景ID")


class TestCaseUpdate(BaseModel):
    """更新测试用例请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    target_url: Optional[str] = None
    user_query: Optional[str] = None
    test_data: Optional[Dict[str, Any]] = None
    expected_result: Optional[str] = None
    priority: Optional[TestCasePriority] = None
    case_type: Optional[TestCaseType] = None
    status: Optional[str] = None


class TestCaseResponse(TestCaseBase):
    """测试用例响应"""
    id: int
    scenario_id: Optional[int] = None
    priority: TestCasePriority
    case_type: TestCaseType
    status: str
    actions: Optional[List[str]] = None
    script: Optional[str] = None
    execution_count: int
    last_execution_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TestCaseGenerateRequest(BaseModel):
    """生成测试用例请求"""
    test_case_id: int


class TestCaseExecuteRequest(BaseModel):
    """执行测试用例请求"""
    test_case_id: int


# ==================== 报告相关 Schemas ====================

class TestStepResultResponse(BaseModel):
    """测试步骤执行结果响应"""
    id: int
    test_report_id: int
    step_number: int
    step_name: str
    step_type: Optional[str] = None
    status: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    execution_duration: Optional[int] = None
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    log_output: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TestReportResponse(BaseModel):
    """测试报告响应"""
    id: int
    test_case_id: int
    test_case_name: Optional[str] = None
    scenario_id: Optional[int] = None
    status: str
    result: Optional[str] = None
    error_message: Optional[str] = None
    execution_time: Optional[int] = None
    screenshot_path: Optional[str] = None
    created_at: datetime
    step_results: Optional[List[TestStepResultResponse]] = None

    class Config:
        from_attributes = True


# ==================== 快速生成相关 Schemas ====================

class QuickGenerateRequest(BaseModel):
    """快速生成测试用例请求"""
    user_query: str = Field(..., description="测试需求描述")
    target_url: str = Field(..., description="目标URL")
    generation_strategy: GenerationStrategy = Field(GenerationStrategy.BASIC, description="生成策略")
    auto_detect_captcha: bool = Field(False, description="是否自动识别验证码")
    use_computer_use: bool = Field(False, description="是否使用 Computer-Use 方案（截图+坐标定位）")


class QuickGenerateResponse(BaseModel):
    """快速生成响应"""
    scenario: Optional[TestScenarioResponse] = None
    test_cases: List[TestCaseResponse] = []
    execution_results: List[Dict[str, Any]] = []
    total_execution_time: Optional[int] = None