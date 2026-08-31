"""Reranker 工具：Multi-Query 多查询生成 + Cross-Encoder 重排序。

1. multi_query_generate：调用 LLM 生成多个角度的子查询，用于多查询召回；
2. rerank_documents：使用 sentence-transformers Cross-Encoder 对检索结果重排序。

设计要点：sentence-transformers 依赖 torch，属于重型依赖，全部在函数内部懒加载；
安装失败或推理异常时自动降级（返回原顺序），不影响主链路。
"""
from typing import List

from langchain_core.documents import Document
from utils.logger import setup_logger

logger = setup_logger("reranker")


def multi_query_generate(original_query: str, llm, num_queries: int = 3) -> List[str]:
    """调用 LLM 从不同角度生成 num_queries 个检索子查询。

    Args:
        original_query: 原始问题。
        llm: LangChain ChatModel 实例。
        num_queries: 生成的子查询数量。

    Returns:
        子查询列表；失败时回退为 [original_query]，保证主链路可用。
    """
    prompt = (
        f"你是检索查询专家。针对原始问题，从不同角度生成 {num_queries} 个用于向量检索的子查询，"
        f"使其相互补充、覆盖更多信息。\n"
        f"只输出每行一个查询，不要编号，不要解释。\n\n"
        f"原始问题：{original_query}"
    )
    try:
        resp = llm.invoke(prompt)
        lines = [l.strip() for l in str(resp.content).splitlines() if l.strip()]
        # 过滤编号/列表前缀
        queries = [l for l in lines if not l[0].isdigit() and not l.startswith(("-", "*", "·"))]
        # 保底：保证子查询里包含原始问题；数量不足时用原问题补足
        merged = [original_query] + queries + [original_query] * num_queries
        return list(dict.fromkeys(merged))[:num_queries] if merged else [original_query]
    except Exception as e:
        logger.warning("multi-query 生成失败，回退原始查询: %s", e)
        return [original_query]


def rerank_documents(
    query: str,
    docs: List[Document],
    top_n: int,
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
) -> List[Document]:
    """使用 Cross-Encoder 对检索结果重排序，返回前 top_n 个文档。

    Args:
        query: 查询文本。
        docs: 召回阶段的文档列表。
        top_n: 重排后返回的数量。
        model_name: Cross-Encoder 模型名。

    Returns:
        重排后的文档列表；失败时降级返回 docs[:top_n]（保持原顺序）。
    """
    if not docs:
        return docs

    # 懒加载 sentence-transformers（依赖 torch，属重型依赖）
    try:
        from sentence_transformers import CrossEncoder
        import numpy as np  # sentence-transformers 的既有依赖，必然可用
    except ImportError as e:
        logger.warning("sentence-transformers 未安装或加载失败，跳过重排: %s", e)
        return docs[:top_n]

    try:
        model = CrossEncoder(model_name)  # CPU 可推理，首次调用需联网下载模型
        pairs = [(query, d.page_content) for d in docs]
        scores = model.predict(pairs)
        # 形状防御：部分 Cross-Encoder 返回 (n,1) 二维数组或标量，统一拍平为一维，
        # 否则 zip+sort+float() 会因数组比较/转换报错
        scores = np.asarray(scores).reshape(-1).tolist()
        ranked = list(zip(docs, scores))
        ranked.sort(key=lambda x: x[1], reverse=True)
        # 打分写入 metadata，供前端调试面板展示
        for d, s in ranked:
            d.metadata["rerank_score"] = round(float(s), 4)
        return [d for d, _ in ranked[:top_n]]
    except Exception as e:
        logger.error("重排执行失败，返回原顺序: %s", e)
        return docs[:top_n]