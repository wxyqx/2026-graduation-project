"""【投递相关的表格模板】

投递的「返回数据」比较复杂（要带候选人、岗位、7 阶段时间线），
所以没写成 pydantic 类，而是在 services/views.py 里用函数拼成字典返回。这里只有「进来的数据」。
"""
from pydantic import BaseModel, Field


class ApplicationCreate(BaseModel):
    """手动新建一条投递：谁（can_id）投了哪个岗位（pos_id）。"""

    can_id: int = Field(description="候选人编号。先去 candidates 新建一个候选人，返回里的 id 就是它")
    pos_id: int = Field(description="岗位编号。先去 positions 新建一个岗位，返回里的 id 就是它")

    model_config = {"json_schema_extra": {"examples": [{"can_id": 1, "pos_id": 1}]}}


class AdvanceIn(BaseModel):
    """推进一关：告诉我「你以为现在在哪一关」（fromStage）和「这关的结果」（result：pass / fail）。

    为什么要传 fromStage？防止手快点两次：第二次点时阶段已经变了，fromStage 对不上就拒绝。
    """

    # alias="fromStage"：前端 JSON 里叫 fromStage（驼峰），Python 里叫 from_stage（下划线），两边各用各的习惯
    from_stage: str = Field(
        alias="fromStage",
        description=(
            "当前在哪一关，必须和投递的 current_stage 一样（先查详情看）。"
            "可选值：ai=AI筛选 / resume=简历筛选 / phone=电话沟通 / "
            "test=笔试 / pro=专业面 / hr=HR面 / final=终面"
        ),
    )
    result: str = Field(description="这一关的结果：pass=通过（进下一关）/ fail=淘汰（流程结束）")

    # 允许两种写法都能传进来（fromStage 或 from_stage）
    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {"examples": [{"fromStage": "ai", "result": "pass"}]},
    }


class RevertIn(BaseModel):
    """撤回：toStage 可以不传（撤销上一步），也可以指定退回到哪一关。"""

    to_stage: str | None = Field(
        default=None,
        alias="toStage",
        description=(
            "想退回到哪一关，可不传。不传 = 撤销上一步（打错分了反悔用）；"
            "传了 = 退回到那一关重新来，那一关之后的成绩全清空。值和 fromStage 一样的 7 个"
        ),
    )

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {"examples": [{}, {"toStage": "resume"}]},
    }
