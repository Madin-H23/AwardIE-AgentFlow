"""
Agent 工具集（Function Calling）

把现有 Manager 的查询/统计/导出能力封装为 LangChain @tool，
供 Agent 自主调用。这是岗位 JD 第 2 条（AI Agent）的直接落地。

设计原则：
- 只封装查询/统计/导出类方法，绝不封装写/删操作（避免 Agent 误改数据）
- 复用现有 Manager，不重写业务逻辑
- 依赖（db_path / config_loader）通过 ToolContext 统一注入
"""
