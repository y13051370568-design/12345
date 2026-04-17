from fastapi import HTTPException, Depends

# 临时模拟（后面再接 JWT）
def get_current_user():
    return {"role": "ADMIN"}  # 测试用


def admin_required(user=Depends(get_current_user)):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="无权限")
    return user