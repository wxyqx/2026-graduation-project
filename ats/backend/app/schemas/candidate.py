"""【候选人相关的表格模板】v3.15 增加手机号 / 邮箱 / 账号状态。"""
from datetime import datetime

from pydantic import BaseModel, Field


class CandidateIn(BaseModel):
    """新建候选人：姓名必填；手机号可选，但填了就会自动开通候选人账号。"""

    name: str = Field(min_length=1, max_length=255, description="姓名（必填）")
    phone: str | None = Field(
        default=None,
        max_length=20,
        description="手机号。填了会自动开通候选人端账号（默认密码 admin）；不填则候选人无法登录",
    )
    email: str | None = Field(default=None, max_length=100, description="邮箱，可不填")
    remark: str | None = Field(default=None, max_length=500, description="备注，可不填。例：内推 / 猎头推荐 / 校招")

    model_config = {
        "json_schema_extra": {"examples": [{"name": "张三", "phone": "13800138000", "remark": "内推"}]}
    }


class CandidateUpdate(BaseModel):
    """编辑候选人：姓名、手机号、邮箱、备注都可以改。

    **关于手机号**：手机号是候选人端登录账号。改了手机号，旧手机号立刻不能登录，新手机号可以登录。
    清空手机号（传空字符串）= 停用这个候选人的登录能力，账号保留。

    **关于改姓名**：AI 识别简历有时会把名字认错，这里提供人工纠正。
    改名不影响任何投递记录——投递是按候选人编号关联的。
    """

    name: str | None = Field(default=None, min_length=1, max_length=255, description="新的姓名，不传=不改")
    phone: str | None = Field(default=None, max_length=20, description="新手机号；传空字符串=清空手机号")
    email: str | None = Field(default=None, max_length=100, description="新邮箱；传空字符串=清空")
    remark: str | None = Field(default=None, max_length=500, description="新的备注。传空字符串可以清空备注")
    # HR 从简历摘录的个人信息（与表单答卷独立）
    onboard_date: str | None = Field(default=None, max_length=50, description="到岗时间，可写「随时」等")
    school: str | None = Field(default=None, max_length=100, description="毕业院校")
    degree: str | None = Field(default=None, max_length=20, description="学历")
    major: str | None = Field(default=None, max_length=100, description="专业")
    expected_salary: str | None = Field(default=None, max_length=50, description="期望薪资")
    work_location: str | None = Field(default=None, max_length=100, description="期望工作地点")
    hire_type: str | None = Field(default=None, max_length=20, description="招聘类型（校招/社招）")
    work_experience: str | None = Field(default=None, description="工作经历")
    confirm_duplicate: bool = Field(
        default=False,
        description="重名确认：改成与已有候选人相同的姓名时，第一次会返回 409；确认无误后带 true 再提交一次即可",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"remark": "已电话确认到岗时间"},
                {"phone": "13900139000"},
                {"name": "樊浩"},
            ]
        }
    }


class CandidateOut(BaseModel):
    """回给前端的候选人信息。"""

    id: int = Field(description="候选人编号。建投递时 can_id 填这个")
    name: str | None = Field(description="姓名")
    owner_id: int | None = Field(default=None, description="负责人 HR 编号；NULL=暂无负责人")
    owner_name: str | None = Field(default=None, description="负责人姓名（实名优先）")
    phone: str | None = Field(default=None, description="手机号（候选人端登录账号）")
    email: str | None = Field(default=None, description="邮箱")
    remark: str | None = Field(description="备注")
    onboard_date: str | None = Field(default=None, description="到岗时间")
    school: str | None = Field(default=None, description="毕业院校")
    degree: str | None = Field(default=None, description="学历")
    major: str | None = Field(default=None, description="专业")
    expected_salary: str | None = Field(default=None, description="期望薪资")
    work_location: str | None = Field(default=None, description="期望工作地点")
    hire_type: str | None = Field(default=None, description="招聘类型")
    work_experience: str | None = Field(default=None, description="工作经历")
    create_time: datetime | None = Field(description="录入时间")
    application_count: int = Field(default=0, description="名下投递数（删除前会连带删除这些）")
    has_account: bool = Field(default=False, description="是否已开通候选人端账号（有手机号即开通）")
