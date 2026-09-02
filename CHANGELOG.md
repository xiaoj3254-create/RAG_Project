# Changelog

## 2026-09-01 — 代码审查修复（6 处，6 个文件）

源自一轮 code-review 发现的真实问题，全部已修复。

### 修复内容

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| 1 | 运行时产物被提交进 git：`logs/rag.log` 已捕获用户查询与错误堆栈；`db/rag.db-wal`/`db/rag.db-shm` 是 SQLite WAL 瞬时文件，`.gitignore` 未覆盖，全新 clone 时主库缺失而 WAL 存在会引发 DB 损坏 | [.gitignore](.gitignore) | 补 `logs/`、`db/rag.db-wal`、`db/rag.db-shm`；已提交的 3 个文件待 `git rm --cached` 从跟踪移除（保留磁盘文件） |
| 2 | 维度自愈逻辑失效：`_check_embedding_compatibility` 只 `store.delete(ids)` 清空向量，collection 的 HNSW 维度元数据仍停留在旧维度，检索依旧报 `expecting embedding with dimension of X`（提交的日志已证实例） | [main.py](main.py) | 改为 `delete_collection` 后按当前 Embedding 重建 `Chroma` 实例，彻底重置维度元数据 |
| 3 | 置信度恒 0.5：DeepSeek-V4-Flash（推理模型）在数值答案里带 `…` 思考块，`float()` 每次抛异常走兜底 | [main.py](main.py) | 解析前先剥离 HTML 风格标签，再 `re` 正则提取首个浮点数并 clamp 到 [0,1]；新增 `import re` |
| 4 | `.env.example` 模板缺失：README（第 73-74 行）让用户 `cp/copy .env.example .env`，但文件从未创建 | [.env.example](.env.example) | 新建模板，覆盖 config.py 全部环境变量，含中文注释与降级演示模式说明 |
| 5 | `get_rag()` 首请求竞态：并发首请求都看到 `_rag` 为 None，各自独立构建 RAGChain（两个 DocumentProcessor/Chroma 实例、两次维度清理），后写者覆写单例 | [api.py](api.py) | 首初始化纳入 `_config_lock`，双检锁 + 锁内二次判空 |
| 6 | `utils/logger.py` 一段 4 行注释块重复两遍，描述同一 Windows stdout 重配置意图 | [utils/logger.py](utils/logger.py) | 删除重复块 |

### 验证情况

- ✅ 全部改动文件（main.py / api.py / config.py / utils/logger.py）`ast` 语法检查通过
- ⚠️ 维度自愈重建 collection 使用了 chromadb 私有属性 `store._client` / `store._name`，需在装有 langchain-chroma 的环境实测

### 建议提交信息

```
fix: code review findings (runtime artifacts, dimension heal, confidence, .env.example)

- gitignore logs/ and sqlite WAL/SHM; drop tracked runtime artifacts (pending git rm --cached)
- rebuild Chroma collection on embedding dimension mismatch instead of only deleting vectors
- strip thinking-block tags before parsing LLM confidence score (DeepSeek reasoning models)
- add missing .env.example template
- serialize get_rag() first init under config lock (double-checked locking)
- dedupe logger.py Windows stdout comment block
```

---

## 2026-08-31 — 代码审查修复（9 处，4 个文件）

源自一轮 code-review 发现的真实问题，全部已修复。

### 修复内容

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| 1 | 前端 chunk_size/chunk_overlap 参数覆盖无效（text_splitter 存的是初始值，改 config 不生效） | [main.py](main.py) | 新增 `DocumentProcessor.rebuild_text_splitter()`，按当前 config 重建 splitter |
| 2 | SimpleEmbeddings(384) ↔ OpenAIEmbeddings(1536) 切换后与持久化 Chroma 维度不匹配，检索静默返空 | [main.py](main.py) | 新增 `_check_embedding_compatibility()`：启动自检维度，不一致时告警并清空 collection 分批重删（1000 条/批） |
| 3 | 幻觉重试是空转：跳回 generate 但 context 相同，仅靠 LLM 随机采样 | [main.py](main.py) | `RAGState` 新增 `hallucination_feedback`；`Generator.generate()` 支持 feedback 参数注入 SystemMessage 纠偏 |
| 4 | SQLite 并发 `database is locked`（FastAPI 线程池多请求同时写） | [db/sqlite_db.py](db/sqlite_db.py) | `_connect()` 加 `timeout=15` + `PRAGMA foreign_keys=ON` + WAL 模式 |
| 5 | 外键未强制，孤儿消息；chat 传不存在的 session_id 打穿 FK | [db/sqlite_db.py](db/sqlite_db.py) / [api.py](api.py) | FK 真正开启；chat 前置校验返回 404 |
| 6 | 历史消息丢失 meta，刷新后来源/置信度/调试面板消失 | [db/sqlite_db.py](db/sqlite_db.py) / [api.py](api.py) | `messages` 表新增 `meta` 列（含旧库 ALTER 迁移）；`save_message` 写 JSON，`get_session_messages` 反序列化；chat 保存时附带 sources/confidence/sub_queries/rerank_scores |
| 7 | chat 覆盖全局单例 config 后从不恢复，参数跨请求/跨会话泄漏 | [api.py](api.py) | 新增 `_config_lock` 互斥锁；快照 → 覆盖 → finally 恢复（含 splitter 同步重建） |
| 8 | reranker `predict()` 对部分模型返回 (n,1) 二维或标量，zip/float 崩溃 | [utils/reranker_helper.py](utils/reranker_helper.py) | `np.asarray(scores).reshape(-1).tolist()` 拍平为一维 |
| 9 | tmp 目录按 CHROMA_DB_PATH 推断反向解析，依赖进程 CWD 而分叉；`file.filename` 可能为 None | [api.py](api.py) | tmp 锚定 `config.ROOT_DIR/tmp`；filename 空值兜底；上传的重关联/建图纳入锁 |

### 未改动

- [frontend.py](frontend.py) — sqlite 返回格式天然兼容前端渲染逻辑
- [utils/file_loader.py](utils/file_loader.py) — 异常捕获/编码回退本就完整
- `.gitignore` — 已覆盖 `tmp/`、`db/chroma_db/`、`db/rag.db`

### 验证情况

- ✅ 全部改动文件 `ast` 语法检查通过
- ✅ sqlite 层（meta 迁移、CRUD、外键、锁）本机实测通过
- ⚠️ 本机未安装 `langchain`，main.py 的检索/重排/Chroma 链路未实测，需在有依赖环境或 Docker 中验证

### 建议提交信息

```
fix: RAG system hardening from code review

- rebuild text_splitter on chunk param override (frontend sliders now effective)
- detect embedding dimension mismatch vs persisted Chroma vectors
- add SQLite busy timeout / WAL / FK enforcement + meta column migration
- persist assistant meta (sources/confidence/debug) for history reload
- serialize chat config override under lock with snapshot restore
- vary hallucination retry via LLM feedback (no futile identical retry)
- guard reranker score shape, tmp dir CWD dependency, filename None
```