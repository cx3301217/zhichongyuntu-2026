# 根目录入口，供 Zeabur 启动命令 uvicorn main:app 使用
# 实际应用逻辑在 backend.app.main

from backend.app.main import app

__all__ = ["app"]
