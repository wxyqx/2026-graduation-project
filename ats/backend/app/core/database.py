"""
【这个文件是干什么的？】
它负责「连上数据库」。

数据库可以想象成一个巨大的仓库，里面有很多货架（表），每个货架上放着很多盒子（记录）。
我们的程序要往仓库里存东西、拿东西，就得先有一条通往仓库的路——这个文件就是修路的。

两个重要角色：
  engine（引擎）      ——通往仓库的大门，整个程序只有一个。
  SessionLocal（会话）——每次去仓库办事时推的小推车：进门、装货/取货、结账（commit）、还车（close）。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# 造一个引擎（大门）。
#   pool_pre_ping=True ：每次用连接前先「敲敲门」确认还通着，防止拿到已经断掉的连接
#   pool_recycle=3600  ：连接用满 1 小时就换新的，MySQL 默认 8 小时不用会自动断，提前换更稳
engine = create_engine(settings.database_url, pool_pre_ping=True, pool_recycle=3600)

# 「小推车工厂」：每调用一次 SessionLocal() 就得到一辆新的小推车（一个数据库会话）
#   autoflush=False      ：不要自动把改动偷偷写进去，等我们说 commit 再写
#   expire_on_commit=False：commit 之后对象里的数据别清空，我们还要拿来返回给前端
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """借一辆小推车（数据库会话），用完一定归还。

    这是 FastAPI 的「依赖」写法：接口函数写上 db: Session = Depends(get_db)，
    FastAPI 就会在处理请求前调用这个函数借车，处理完自动执行 finally 里的还车。
    yield 就是「先把车交出去，等对方用完再回到这里继续往下走」。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
