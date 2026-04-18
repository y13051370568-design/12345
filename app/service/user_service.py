from app.models.user import User

def get_user_list(db, page, page_size, role=None, status=None, username=None):
    query = db.query(User)

    if username:
        query = query.filter(User.username.like(f"%{username}%"))

    if role:
        query = query.filter(User.role == role)

    if status is not None:
        query = query.filter(User.status == status)

    total = query.count()

    users = query.offset((page - 1) * page_size).limit(page_size).all()

    return total, users


def update_user_role(db, user_id, role):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise Exception("用户不存在")

    user.role = role
    db.commit()


def toggle_user_status(db, user_id, status):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise Exception("用户不存在")

    user.status = status
    db.commit()