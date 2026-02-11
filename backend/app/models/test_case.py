from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from sqlalchemy.orm import declarative_base

# 创建基类（避免循环导入）
Base = declarative_base()


class TestCasePriority(enum.Enum):
    """测试用例优先级"""
    P0 = "P0"  # 冒烟测试，核心功能
    P1 = "P1"  # 重要功能
    P2 = "P2"  # 一般功能
    P3 = "P3"  # 边缘功能


class TestCaseType(enum.Enum):
    """测试用例类型"""
    POSITIVE = "positive"  # 正向测试
    NEGATIVE = "negative"  # 负向测试
    BOUNDARY = "boundary"  # 边界测试
    EXCEPTION = "exception"  # 异常测试
    SECURITY = "security"  # 安全测试
    PERFORMANCE = "performance"  # 性能测试
    COMPATIBILITY = "compatibility"  # 兼容性测试


class TestScenario(Base):
    """测试场景模型 - 一个场景对应多个用例"""
    __tablename__ = "test_scenarios"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, comment="场景名称")
    description = Column(Text, comment="场景描述")
    target_url = Column(String(500), nullable=False, comment="目标URL")
    user_query = Column(Text, nullable=False, comment="用户自然语言描述的场景")
    generation_strategy = Column(String(50), default="basic", comment="生成策略: happy_path, basic, comprehensive")
    total_cases = Column(Integer, default=0, comment="生成的用例总数")
    status = Column(String(50), default="draft", comment="状态: draft, generating, completed, failed")
    
    # 登录配置
    login_config = Column(String(50), default="no_login", comment="登录配置: no_login, perform_login, use_global_session, use_session")
    session_id = Column(Integer, ForeignKey("test_sessions.id", ondelete="SET NULL"), comment="使用的会话ID")
    save_session = Column(Boolean, default=False, comment="是否保存会话")
    
    # 验证码和 Cookie/LocalStorage 配置
    use_captcha = Column(Boolean, default=False, comment="是否使用验证码")
    auto_cookie_localstorage = Column(Boolean, default=True, comment="自动加载和保存 cookie/localstorage")
    load_saved_storage = Column(Boolean, default=True, comment="是否加载保存的cookie/localstorage/sessionstorage")
    
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 关系
    test_cases = relationship("TestCase", back_populates="scenario", cascade="all, delete-orphan")
    session = relationship("TestSession", foreign_keys=[session_id])


class TestCase(Base):
    """测试用例模型"""
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(Integer, ForeignKey("test_scenarios.id"), nullable=False, comment="所属场景ID")
    name = Column(String(255), nullable=False, comment="测试用例名称")
    description = Column(Text, comment="测试用例描述")
    target_url = Column(String(500), nullable=False, comment="目标URL")
    user_query = Column(Text, nullable=False, comment="用例的具体测试需求")
    test_data = Column(JSON, comment="测试数据，如输入参数等")
    expected_result = Column(Text, comment="预期结果")
    actions = Column(JSON, comment="生成的操作步骤")
    script = Column(Text, comment="生成的Playwright脚本")
    priority = Column(SQLEnum(TestCasePriority), default=TestCasePriority.P1, comment="优先级: P0, P1, P2, P3")
    case_type = Column(SQLEnum(TestCaseType), default=TestCaseType.POSITIVE, comment="用例类型")
    status = Column(String(50), default="draft", comment="状态: draft, generated, executing, completed, failed")
    execution_count = Column(Integer, default=0, comment="执行次数")
    last_execution_at = Column(DateTime, comment="最后执行时间")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 关系
    scenario = relationship("TestScenario", back_populates="test_cases")
    test_reports = relationship("TestReport", back_populates="test_case", cascade="all, delete-orphan")


class TestReport(Base):
    """测试报告模型"""
    __tablename__ = "test_reports"

    id = Column(Integer, primary_key=True, index=True)
    test_case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=False, comment="测试用例ID")
    scenario_id = Column(Integer, ForeignKey("test_scenarios.id"), comment="场景ID")
    status = Column(String(50), nullable=False, comment="测试状态: passed, failed, error")
    result = Column(Text, comment="测试结果详情")
    error_message = Column(Text, comment="错误信息")
    execution_time = Column(Integer, comment="执行时间(毫秒)")
    screenshot_path = Column(String(500), comment="截图路径")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    # 关系
    test_case = relationship("TestCase", back_populates="test_reports")
    step_results = relationship("TestStepResult", back_populates="test_report", cascade="all, delete-orphan")
    
    # 动态属性（用于 API 响应）
    test_case_name = None


class TestStepResult(Base):
    """测试步骤执行结果模型 - 记录每一步的执行详情"""
    __tablename__ = "test_step_results"

    id = Column(Integer, primary_key=True, index=True)
    test_report_id = Column(Integer, ForeignKey("test_reports.id"), nullable=False, comment="测试报告ID")
    step_number = Column(Integer, nullable=False, comment="步骤序号")
    step_name = Column(String(500), nullable=False, comment="步骤名称/描述")
    step_type = Column(String(50), comment="步骤类型: navigation, click, fill, verify, wait, screenshot等")
    status = Column(String(50), nullable=False, comment="执行状态: pending, running, passed, failed, skipped")
    start_time = Column(DateTime, comment="开始执行时间")
    end_time = Column(DateTime, comment="结束执行时间")
    execution_duration = Column(Integer, comment="执行时长(毫秒)")
    input_data = Column(JSON, comment="输入数据")
    output_data = Column(JSON, comment="输出数据")
    error_message = Column(Text, comment="错误信息")
    screenshot_path = Column(String(500), comment="步骤截图路径")
    log_output = Column(Text, comment="步骤执行日志")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    # 关系
    test_report = relationship("TestReport", back_populates="step_results")