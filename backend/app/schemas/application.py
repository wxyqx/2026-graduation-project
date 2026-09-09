"""【投递相关的表格模板】

投递的「返回数据」比较复杂（要带候选人、岗位、8 阶段时间线），
所以没写成 pydantic 类，而是在 services/views.py 里用函数拼成字典返回。这里只有「进来的数据」。
"""
from pydantic import BaseModel, Field


class ApplicationCreate(BaseModel):
    """手动新建一条投递：谁（can_id）投了哪个岗位（pos_id）。"""

    can_id: int
    pos_id: int


class AdvanceIn(BaseModel):
    """推进一关：告诉我「你以为现在在哪一关」（fromStage）和「这关的结果」（result：pass / fail）。

    为什么要传 fromStage？防止手快点两次：第二次点时阶段已经变了，fromStage 对不上就拒绝。
    """

    # alias="fromStage"：前端 JSON 里叫 fromStage（驼峰），Python 里叫 from_stage（下划线），两边各用各的习惯
    from_stage: str = Field(alias="fromStage")
    result: str

    # 允许两种写法都能传进来（fromStage 或 from_stage）
    model_config = {"populate_by_name": True}


class RevertIn(BaseModel):
    """撤回：toStage 可以不传（撤销上一步），也可以指定退回到哪一关。"""

    to_stage: str | None = Field(default=None, alias="toStage")

    model_config = {"populate_by_name": True}
