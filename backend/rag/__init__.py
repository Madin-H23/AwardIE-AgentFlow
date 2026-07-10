"""
RAG 模块

基于向量检索构建竞赛规则知识库，支持自然语言问答。

子模块说明：
- embeddings: Embedding Provider 封装（智谱 embedding-3 等）
- vectorstore: Chroma 向量库管理（持久化到 database/chroma/）
- indexer: 知识入库（竞赛等级分类表 docx → 切分 → 向量化）
- retriever: 检索器（MMR + 元数据过滤）
"""
