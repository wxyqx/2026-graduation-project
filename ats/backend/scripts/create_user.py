"""
【创建 / 管理后台账号的小工具】——技术管理员、HR 账号

候选人账号不在这里建：候选人只要档案里有手机号，系统会自动开通（阶段 2 实现）。

用法（在 backend 目录下执行）：
    .venv\\Scripts\\python scripts\\create_user.py --list
    .venv\\Scripts\\python scripts\\create_user.py --role admin --username tech --password admin123
    .venv\\Scripts\\python scripts\\create_user.py --role hr --username hr01 --password admin123
    .venv\\Scripts\\python scripts\\create_user.py --username tech --password newpass --reset

参数说明：
    --role      admin（技术管理员）或 hr（HR）
    --username  登录用户名
    --password  密码，不填默认 admin
    --reset     账号已存在时只重置角色与密码
    --disable / --enable  停用 / 启用账号
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

# 让脚本能 import app.*（把 backend 目录加进搜索路径）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import User
from app.services.security import hash_password

ROLES = ("admin", "hr")


def list_users(db) -> None:
    rows = db.scalars(select(User).order_by(User.id)).all()
    if not rows:
        print("（还没有任何账号）")
        return
    print(f"{'ID':>4}  {'用户名':<20} {'角色':<10} {'状态':<6} {'候选人ID':<8} 最近登录")
    print("-" * 78)
    for u in rows:
        name = u.username or "(手机号账号)"
        state = "启用" if getattr(u, "is_active", 1) else "停用"
        last = u.last_login_time.strftime("%Y-%m-%d %H:%M") if u.last_login_time else "-"
        print(f"{u.id:>4}  {name:<20} {u.role:<10} {state:<6} {u.candidate_id or '-'!s:<8} {last}")


def main() -> int:
    parser = argparse.ArgumentParser(description="创建 / 管理 HR 与技术管理员账号")
    parser.add_argument("--role", choices=ROLES, help="账号角色：admin 或 hr")
    parser.add_argument("--username", help="登录用户名")
    parser.add_argument("--password", default="admin", help="密码，默认 admin")
    parser.add_argument("--phone", help="手机号，11 位（新建时必填）")
    parser.add_argument("--real-name", help="实名（新建时必填）")
    parser.add_argument("--reset", action="store_true", help="账号已存在时重置角色与密码")
    parser.add_argument("--disable", action="store_true", help="停用账号")
    parser.add_argument("--enable", action="store_true", help="启用账号")
    parser.add_argument("--list", action="store_true", help="列出所有账号")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.list:
            list_users(db)
            return 0

        if not args.username:
            parser.error("请提供 --username（或用 --list 查看账号）")

        user = db.scalar(select(User).where(User.username == args.username))

        if args.disable or args.enable:
            if user is None:
                print(f"找不到账号：{args.username}")
                return 1
            user.is_active = 0 if args.disable else 1
            db.commit()
            print(f"已{'停用' if args.disable else '启用'}：{args.username}")
            return 0

        if user is not None and not args.reset:
            print(f"账号已存在：{args.username}（角色 {user.role}）。要重置请加 --reset")
            return 1

        if user is None:
            if not args.role:
                parser.error("新建账号必须指定 --role admin 或 --role hr")
            # 手机号必填：与接口口径一致（HR/管理员个人信息强制要求有手机号）
            from app.services.phone import is_valid_phone, normalize_phone

            phone = normalize_phone(args.phone)
            if not is_valid_phone(phone):
                parser.error("新建账号必须提供合法手机号：--phone 13800138000")
            dup = db.scalar(select(User.id).where(User.phone == phone))
            if dup:
                print(f"手机号已被其他账号使用：{phone}")
                return 1
            real_name = (args.real_name or "").strip()
            if not (2 <= len(real_name) <= 50):
                parser.error("新建账号必须提供实名：--real-name 张三")
            user = User(
                username=args.username,
                phone=phone,
                real_name=real_name,
                password_hash=hash_password(args.password),
                role=args.role,
                is_active=1,
                create_time=datetime.now(),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"已创建 {args.role} 账号：{args.username}（ID={user.id}），密码：{args.password}")
        else:
            if args.role:
                user.role = args.role
            user.password_hash = hash_password(args.password)
            user.is_active = 1
            db.commit()
            print(f"已重置：{args.username}，角色 {user.role}，密码 {args.password}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
