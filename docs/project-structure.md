# DeployMate - 运维实施工程师记录助手

## 项目结构
```
DeployMate/
├── src/
│   ├── __init__.py
│   ├── main.py                 # 程序入口
│   ├── models/                 # 数据模型
│   │   ├── __init__.py
│   │   ├── base.py            # SQLAlchemy基类
│   │   ├── project.py         # 项目模型
│   │   ├── machine.py         # 机器模型
│   │   ├── daily_report.py    # SOP问题记录模型（兼容旧表名）
│   │   ├── expense.py         # 费用模型
│   │   └── import_file.py     # 导入文件模型
│   ├── ui/                     # PySide6界面
│   │   ├── __init__.py
│   │   ├── main_window.py     # 主窗口
│   │   ├── pages/             # 各页面
│   │   │   ├── __init__.py
│   │   │   ├── home_page.py
│   │   │   ├── project_page.py
│   │   │   ├── machine_page.py
│   │   │   ├── import_page.py
│   │   │   ├── daily_page.py
│   │   │   ├── expense_page.py
│   │   │   ├── export_page.py
│   │   │   └── settings_page.py
│   │   └── widgets/           # 公共组件
│   │       ├── __init__.py
│   │       └── common.py
│   ├── services/              # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── project_service.py
│   │   ├── machine_service.py
│   │   ├── import_service.py  # 导入合并逻辑
│   │   ├── export_service.py  # 导出逻辑
│   │   └── db_service.py      # 数据库初始化
│   └── utils/                 # 工具函数
│       ├── __init__.py
│       ├── excel_parser.py    # Excel解析
│       ├── word_parser.py     # Word解析
│       └── field_mapper.py    # 字段识别映射
├── data/                      # 本地数据目录
│   └── deploymate.db         # SQLite数据库（运行时生成）
├── docs/                      # 文档
│   └── database-design.md
├── tests/                     # 测试
│   └── __init__.py
├── requirements.txt           # Python依赖
├── README.md
└── .gitignore
```

## 开发顺序
1. 数据库模型（models/）
2. 数据库服务（services/db_service.py）
3. 主窗口框架（ui/main_window.py）
4. 首页（ui/pages/home_page.py）
5. 项目管理页（ui/pages/project_page.py）
6. 机器信息页（ui/pages/machine_page.py）
7. 导入合并页（ui/pages/import_page.py）
8. SOP问题记录/费用页
9. 导出功能
10. 打包成 exe
