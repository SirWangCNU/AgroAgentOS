# Alembic 数据库迁移

本目录包含 AgroAgentOS 项目的数据库迁移文件。

## 目录结构

```
alembic/
├── env.py              # 迁移环境配置
├── script.py.mako      # 迁移脚本模板
├── versions/           # 迁移版本文件
│   └── 001_initial_migration.py  # 初始迁移
└── README.md           # 本文件
```

## 使用方法

### 1. 生成新的迁移脚本

当你修改了 SQLAlchemy 模型后，可以自动生成迁移脚本：

```bash
cd e:/GithubProgram/AgroAgentOS
.venv/Scripts/python -m alembic revision --autogenerate -m "描述你的变更"
```

### 2. 执行迁移

应用所有待执行的迁移：

```bash
.venv/Scripts/python -m alembic upgrade head
```

### 3. 回滚迁移

回滚到上一个版本：

```bash
.venv/Scripts/python -m alembic downgrade -1
```

回滚到特定版本：

```bash
.venv/Scripts/python -m alembic downgrade <revision_id>
```

### 4. 查看迁移历史

```bash
.venv/Scripts/python -m alembic history
```

### 5. 查看当前版本

```bash
.venv/Scripts/python -m alembic current
```

## 配置说明

- **数据库路径**: `alembic.ini` 中配置，当前为 `sqlite:///./data/agro_agent.db`
- **模型导入**: `env.py` 中导入 `app.core.sqlite.Base` 作为元数据源
- **版本文件**: 存储在 `versions/` 目录下

## 注意事项

1. 每次修改 ORM 模型后，都需要生成并执行迁移脚本
2. 迁移脚本会自动检测模型与数据库的差异
3. 在生产环境执行迁移前，请先在测试环境验证
4. 重要数据迁移建议先备份数据库
