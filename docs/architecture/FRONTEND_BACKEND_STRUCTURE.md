# 前后端分离项目结构

```text
ShizukuClaw/
├── frontend/                  # 前端项目
│   ├── public/
│   ├── src/
│   │   ├── assets/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── layouts/
│   │   ├── router/
│   │   ├── store/
│   │   ├── services/
│   │   ├── utils/
│   │   └── main.ts
│   ├── .env
│   ├── package.json
│   └── vite.config.ts
├── backend/                   # 后端项目
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── db/
│   │   └── main.py
│   ├── tests/
│   ├── .env
│   ├── requirements.txt
│   └── Dockerfile
├── shared/                    # 前后端共享资源
│   ├── types/
│   ├── constants/
│   └── api-contracts/
├── docs/                      # 接口与项目文档
│   ├── api/
│   ├── architecture/
│   └── deployment/
├── scripts/                   # 构建、部署、初始化脚本
├── docker-compose.yml
├── .gitignore
├── README.md
└── LICENSE
```

## 说明

- `frontend/` 只放前端页面、状态管理、路由和调用接口的代码。
- `backend/` 只放后端 API、业务逻辑、数据库访问和测试代码。
- `shared/` 用来放前后端都要用到的类型定义、常量和接口约定。
- `docs/` 用来统一存放接口文档、架构说明和部署说明。
- 根目录只保留部署编排、通用配置和说明文件。