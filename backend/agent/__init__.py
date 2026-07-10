"""
Agent 模块

基于 LangChain + LangGraph 构建 AI Agent 能力，复用现有 config/settings.json 的多 Provider 配置。

子模块说明：
- llm_adapter: 把现有 LLM Provider 配置适配为 LangChain ChatModel
- state: 多智能体协作的共享状态定义
- tools: Function Calling 工具集（封装现有 Manager 业务能力）
- graph: LangGraph 多智能体编排（Supervisor 模式）
- service: 对外统一入口 AgentService
"""
