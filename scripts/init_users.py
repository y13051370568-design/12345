"""
初始化测试用户脚本
创建三种角色的测试账号
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db import SessionLocal, engine, Base
from app.service.auth_service import auth_service


def init_test_users():
    """初始化测试用户"""
    # 创建数据库表
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        # 测试用户列表
        test_users = [
            {
                "username": "admin",
                "password": "admin123",
                "role": "ADMIN",
                "description": "管理员账号"
            },
            {
                "username": "developer",
                "password": "dev123",
                "role": "DEVELOPER",
                "description": "开发者账号"
            },
            {
                "username": "user",
                "password": "user123",
                "role": "ZERO_BASIS",
                "description": "零基础用户账号"
            }
        ]

        print("=" * 60)
        print("开始创建测试用户...")
        print("=" * 60)

        for user_data in test_users:
            try:
                user = auth_service.register_user(
                    db=db,
                    username=user_data["username"],
                    password=user_data["password"],
                    role=user_data["role"]
                )
                print(f"✓ 创建成功: {user_data['username']} ({user_data['description']})")
                print(f"  - 用户名: {user_data['username']}")
                print(f"  - 密码: {user_data['password']}")
                print(f"  - 角色: {user_data['role']}")
                print()
            except Exception as e:
                print(f"✗ 创建失败: {user_data['username']} - {str(e)}")
                print()

        print("=" * 60)
        print("测试用户创建完成！")
        print("=" * 60)
        print("\n登录测试账号：")
        print("1. 管理员：admin / admin123")
        print("2. 开发者：developer / dev123")
        print("3. 普通用户：user / user123")
        print()

    except Exception as e:
        print(f"错误：{str(e)}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    init_test_users()
