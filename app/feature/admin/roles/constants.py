USER_MANAGEMENT_PERMISSIONS = {
    "users.read": {
        "name": "Xem người dùng",
        "description": "Xem danh sách và chi tiết người dùng",
        "module": "users",
    },
    "users.create": {
        "name": "Tạo người dùng",
        "description": "Tạo tài khoản người dùng mới",
        "module": "users",
    },
    "users.update": {
        "name": "Cập nhật người dùng",
        "description": "Chỉnh sửa thông tin tài khoản người dùng",
        "module": "users",
    },
    "users.deactivate": {
        "name": "Khóa người dùng",
        "description": "Vô hiệu hóa tài khoản người dùng",
        "module": "users",
    },
    "users.delete": {
        "name": "Xóa người dùng",
        "description": "Xóa mềm tài khoản người dùng",
        "module": "users",
    },
    "roles.read": {
        "name": "Xem vai trò",
        "description": "Xem danh sách và chi tiết vai trò",
        "module": "roles",
    },
    "roles.create": {
        "name": "Tạo vai trò",
        "description": "Tạo vai trò mới",
        "module": "roles",
    },
    "roles.update": {
        "name": "Cập nhật vai trò",
        "description": "Cập nhật thông tin vai trò",
        "module": "roles",
    },
    "roles.delete": {
        "name": "Xóa vai trò",
        "description": "Xóa vai trò",
        "module": "roles",
    },
}

DEFAULT_PERMISSION_CODES = set(USER_MANAGEMENT_PERMISSIONS)
