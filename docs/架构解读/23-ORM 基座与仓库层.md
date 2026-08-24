## ORM 基座与仓库层

### 模块定位

本层是系统从旧式手写 `*Manager` 数据访问向 SQLAlchemy ORM 化迁移的基座。它解决三个问题：

1. **连接契约统一**：`backend/orm/base.py` 复用 `utils.db_connection` 的 G1 连接契约（WAL、外键、busy_timeout），通过 `create_engine` 的 `connect` 事件为每个 SQLite 连接设置 PRAGMA，保证 ORM 读写与手写 SQL 路径行为一致。
2. **模型声明底座**：`Base(DeclarativeBase)` 是所有 ORM 模型的父类，采用 SQLAlchemy 2.0 风格（`Mapped` / `mapped_column`）声明字段。
3. **渐进式仓库替代**：`repositories.py` 中的 `UserRepository` 是 Manager 退位试点——先以只读方法接管旧三表逐查的读路径，再以白名单写方法接管 admin 创建/重置/改密等写路径。

模块注释明确表达了设计意图：**“先定义 users 等核心模型，Manager 逐表退化为 Repository”**，即本层是 ORM 化的起点而非终点。

### Engine 与 Session 生命周期

`base.py` 提供四个核心函数：

| 函数 | 职责 | 关键点 |
|------|------|--------|
| `build_engine(db_path)` | 创建引擎 | 路径经 `resolve()` 后替换反斜杠为 `/`，避免 Windows 下 SQLite URL 解析错误；监听 `connect` 事件设置 PRAGMA |
| `get_engine()` | 进程级单例 | 惰性初始化，全局唯一 engine |
| `get_session()` | 创建 Session | 惰性创建 `sessionmaker(bind=engine, future=True)`，每次返回新 Session |
| `reset_engine()` | 重置单例 | 供测试和配置热更新场景使用 |

PRAGMA 设置沿袭 G1 契约：

```sql
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=30000;
PRAGMA journal_mode=WAL;
```

`get_session()` 的契约是**请求内用完即 close**——`UserRepository` 的所有方法都在 `finally` 块中关闭 Session。当前没有上下文管理器或请求级自动关闭装饰器，调用方需自行保证关闭。

### 声明式基类与模型体系

所有模型继承 `Base`，已读源码覆盖五个模型：

| 模型 | 表名 | 职责 |
|------|------|------|
| `User` | `users` | 合并后的单一用户表，替代旧 admins/students/teachers 三表，字段覆盖学生（major/grade）与教师（title/department/id_number）角色属性 |
| `Award` | `awards` | 奖状记录，包含 OCR/抽取结果、竞赛信息、提交者（submitter_id = users.id） |
| `PendingAchievement` | `pending_achievements` | 待审核成果，`achievement_data` 存 JSON 长文本，`is_valid` 为 VIRTUAL 生成列 |
| `AuditLog` | `achievement_audit_log` | 审计日志，记录操作者、trace_id、变更明细 JSON |
| `SystemEventLog` | `system_event_log` | 系统事件（ocr/llm/breaker/auth 等分类），`operator_id` 带 FK → users.id |

设计上的两个显著特征：

- **无 ORM relationship 关联**：除 `SystemEventLog.operator_id` 外，模型间通过整数 ID（`submitter_id`、`reviewer_id`、`competition_id`）隐式关联，未定义 `relationship()`。这与旧表视图化过渡期的策略一致——跨表查询仍走手写 SQL 或显式 join，避免 ORM 关联在迁移过程中产生不一致。
- **字段类型规范化（G8）**：字符串字段标注 `String(N)` 对应目标 VARCHAR(N)，注释说明 SQLite 下仍为 TEXT affinity，但迁移 MySQL/PG 时语义正确；长文本（OCR 结果、JSON）显式使用 `Text`。

`PendingAchievement.is_valid` 是一个值得注意的生成列：

```python
Computed(
    "CASE WHEN json_extract(validation_result, '$.is_valid') IS NULL THEN NULL "
    "ELSE CAST(json_extract(validation_result, '$.is_valid') AS INTEGER) END",
    persisted=False
)
```

它由 `validation_result` JSON 中的 `is_valid` 字段推导，VIRTUAL 生成列不落盘，查询时实时计算，与 M3 落地方案一致。

### 仓库层：UserRepository

`UserRepository` 是当前唯一的 Repository 实现，全部为静态方法，每个方法独立开 Session、独立 commit。读写两套路径：

**读路径（替代旧三表逐查）**

- `get_by_login_code(login_code)` → 按登录号查单用户
- `get_by_id(user_id)` → 按主键查
- `list_by_role(role)` → 按角色列用户

**写路径（admin 操作走 users 真源）**

- `create_user(...)` → 幂等创建/更新，返回 `users.id`；同 `login_code` 已存在时更新资料字段
- `update_password(...)` → 更新密码与 `needs_password_change` 标记，返回受影响行数
- `update_profile(...)` → 白名单更新资料字段
- `deactivate(login_code)` → 软删（`user_activated=0`），保留历史引用
- `update_login_code(old_code, new_code)` → 变更登录号，`users.id` 不变

白名单机制是写路径的安全核心：

```python
_PROFILE_FIELDS = frozenset({
    "name", "role", "user_activated", "phone", "qq", "skills",
    "profile_is_public", "major", "grade", "title", "department",
    "id_number",
})
```

所有写方法只允许更新白名单内的字段，主键字段（`login_code`）与白名单外字段一律不写，防止调用方误传危险字段。

### 调用链

```mermaid
flowchart TD
    subgraph 基础设施
        CL[config.loader.get_config]
        BE[base.build_engine]
        GE[base.get_engine]
        GS[base.get_session]
    end

    subgraph 模型层
        U[users.User]
        A[awards.Award]
        P[pending.PendingAchievement]
        AL[audit_log.AuditLog]
        SE[system_event_log.SystemEventLog]
    end

    subgraph 仓库层
        UR[repositories.UserRepository]
    end

    subgraph 业务调用方
        AUTH[认证与会话管理]
        ADMIN[管理后台用户管理]
        API[/api 蓝图]
    end

    CL -->|db_path| BE
    BE --> GE
    GE --> GS
    GS --> UR
    GS -->|查询语句| U
    GS -->|查询语句| A
    GS -->|查询语句| P
    GS -->|查询语句| AL
    GS -->|查询语句| SE
    UR -->|select/insert/update| U
    AUTH -->|get_by_login_code| UR
    ADMIN -->|create_user / deactivate / update_password| UR
    API -->|update_profile / update_login_code| UR
```

调用链关键节点：

1. **配置 → engine**：`build_engine` 从 `config.loader` 读取 `competitions_db` 路径，构造带 PRAGMA 的 SQLite engine；`get_engine()` 保证进程内单例。
2. **engine → session**：`get_session()` 通过 sessionmaker 创建独立 Session，业务方法使用后必须 close。
3. **repository → model**：`UserRepository` 使用 SQLAlchemy 2.0 `select()` 语句作用于 `User` 模型，通过 `scalar_one_or_none()` / `scalars()` 提取结果。
4. **业务 → repository**：认证模块通过 `get_by_login_code` 取代旧三表逐查；管理后台通过写方法操作 users 真源表。

### 关键状态

- **Session 状态**：每次调用独立创建、独立关闭，无跨方法事务；写方法内部 commit。
- **用户激活状态**：`user_activated=1` 正常，`user_activated=0` 软删；`deactivate` 不物理删除，避免 `pending_achievements` / `awards` 等表的 `submitter_id` 悬空（源码注释明确说明这些表无 FK 约束）。
- **强制改密状态**：`needs_password_change=1` 表示首次登录或管理员重置后需改密，`update_password` 成功后置 0。
- **密码变更语义**：`update_login_code` 变更登录号，`users.id` 不变——业务表通过 `submitter_id` 引用 id，因此变更号不影响历史数据关联；新号若已存在，SQLite 抛 `IntegrityError` 由调用方捕获。

### 边界条件

1. **SQLite 专用**：PRAGMA 设置、路径正斜杠替换均为 SQLite 适配；注释提示字段类型已为 MySQL/PG 迁移做好准备。
2. **无 FK 约束的表**：`awards` / `pending_achievements` 的 `submitter_id` 没有外键约束，因此用户删除只能软删；若物理删除会留下悬空引用。
3. **唯一约束冲突**：`users.login_code` 有 UNIQUE 约束，`update_login_code` 换到已存在的新号时抛 `IntegrityError`，当前仓库不捕获，由调用层处理。
4. **JSON 生成列依赖 SQLite JSON 函数**：`is_valid` 的 `Computed` 表达式使用 `json_extract`，迁移其他数据库时需要重写。
5. **Session 关闭纪律**：当前无请求级自动管理，`get_session()` 后若忘记 close 会造成连接泄漏；Repository 内部已保证关闭，但业务代码直接 `get_session()` 时需自行负责。
6. **并发写**：`create_user` 的“先查后写”不是原子操作，两个并发请求可能同时查到 None 并分别插入，依赖 `login_code` 唯一约束兜底。

### 扩展点

- **新 Repository**：`UserRepository` 是模板，其他核心表（`Award`、`PendingAchievement`）可按同样模式实现 Repository，逐步替换手写 Manager。读方法用 `select()`，写方法注意白名单与幂等。
- **复杂查询**：当前 `UserRepository` 仅覆盖单表简单查询；如需要聚合/联表，可在仓库中增加使用 `func` / `join` 的方法。
- **事务扩展**：当前每个方法独立事务，如出现跨表写需求，可引入 `get_session()` 后由调用方统一 commit/rollback 的模式。
- **生成列模式**：`PendingAchievement.is_valid` 的 `Computed` 表达了一种“由 JSON 字段推导布尔值”的模式，后续可在其他带 `validation_result` 的表复用。
- **engine 热切换**：`reset_engine()` 为配置热更新、测试隔离预留了入口；新环境初始化、迁移脚本可复用 `build_engine` 的 PRAGMA 契约。
- **数据库迁移**：模型字段类型 `String(N)` 与注释中的“迁移 MySQL/PG 时语义正确”表明，模型定义已为 Alembic 跨库迁移预留语义。

### Sources

Sources: [backend/orm/base.py](backend/orm/base.py#L1-L66), [backend/orm/repositories.py](backend/orm/repositories.py#L1-L158), [backend/orm/users.py](backend/orm/users.py#L1-L38), [backend/orm/awards.py](backend/orm/awards.py#L1-L43), [backend/orm/pending.py](backend/orm/pending.py#L1-L45), [backend/orm/audit_log.py](backend/orm/audit_log.py#L1-L26), [backend/orm/system_event_log.py](backend/orm/system_event_log.py#L1-L25)