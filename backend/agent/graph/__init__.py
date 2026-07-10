"""
LangGraph 多智能体编排

采用 Supervisor 模式：一个主管 Agent 负责路由，三个专业 Agent 负责执行。

架构：
    用户请求
       ↓
    [Supervisor] ──路由──┐
       ↓        ↓        ↓
    [抽取Agent][审核Agent][问答Agent]
       ↓        ↓        ↓
       └─── 汇总到 Supervisor ───┘
                ↓
           [最终决策]

每个 Agent 是 StateGraph 的一个节点，读写共享的 AgentState。
"""
