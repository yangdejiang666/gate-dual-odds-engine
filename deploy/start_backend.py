"""
启动后端 FastAPI 服务
绑定 127.0.0.1:8000
"""

import uvicorn
from backend.app.config import settings

if __name__ == "__main__":
    print(f"正在启动 {settings.APP_NAME} 后端服务: http://{settings.HOST}:{settings.PORT}")
    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        log_level="info"
    )
