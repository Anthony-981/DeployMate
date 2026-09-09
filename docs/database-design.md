# DeployMate 数据库设计

## 技术栈
- SQLite 本地数据库
- SQLAlchemy ORM

## 表结构设计

### 1. projects 项目表
- id: 主键
- name: 项目名称
- customer: 客户名称
- project_code: 项目编号（唯一）
- location: 实施地点
- start_date: 开始日期
- end_date: 结束日期
- sales: 销售
- status: 项目状态（待开始/实施中/已完成/已归档）
- remarks: 项目备注
- created_at, updated_at: 时间戳

### 2. machines 机器信息表
- id: 主键
- project_id: 关联项目
- ip: IP地址（按 IP 唯一识别）
- hostname: 主机名
- os: 操作系统
- cpu: CPU
- memory: 内存
- gpu: GPU
- cuda: CUDA版本
- docker: Docker版本
- account: 账号
- password: 密码
- remarks: 备注
- 唯一约束: (project_id, ip)

### 3. daily_reports SOP问题记录表（保留旧表名以兼容已有数据库）
- id: 主键
- project_id: 关联项目
- report_date: 日期
- work_content: SOP主题/步骤
- problems: 遇到的问题
- solutions: 解决方法
- next_plan: 后续建议
- remarks: 备注
- status: 草稿/已完成
- 唯一约束: (project_id, report_date)

### 4. expenses 出差费用表
- id: 主键
- project_id: 关联项目
- expense_date: 日期
- expense_type: 费用类型（交通/住宿/餐费/打车/其他）
- amount: 金额
- remarks: 备注
- is_reimbursed: 报销状态（未提交/已提交/已报销）

### 5. import_files 导入文件记录表
- id: 主键
- project_id: 关联项目
- file_name: 文件名
- file_type: 文件类型
- records_count: 识别记录数
- new_count: 新增数
- merge_count: 合并数
- conflict_count: 冲突数
- status: 待分析/已识别/已合并/冲突
- imported_at: 导入时间
