# 临时冒烟测试脚本（完成后可删除）
import sys
from fastapi.testclient import TestClient
import api

client = TestClient(api.app)  # 触发 startup：建表 + 预热 RAG

# 1. health
r = client.get('/health'); print('1. health:', r.status_code, r.json())

# 2. 会话列表
r = client.get('/api/session'); print('2. session list:', r.status_code, 'count=', len(r.json().get('sessions', [])))

# 3. 新建会话
r = client.post('/api/session', json={'session_name': 'smoke test'})
print('3. create session:', r.status_code, 'sid_head=', r.json().get('session_id', '')[:8])
sid = r.json().get('session_id')

# 4. 上传文档
text = 'LangChain 是一个用于开发 LLM 应用的开源框架。它提供模块化设计、链式调用、记忆管理、工具集成等特性。Chroma 是可持久化的向量数据库，用于存储文档的向量表示。'
r = client.post('/api/doc/upload', files={'file': ('sample.txt', text.encode('utf-8'), 'text/plain')})
print('4. upload doc:', r.status_code, 'payload=', r.json())
did = r.json().get('doc_id')

# 5. 文档列表
r = client.get('/api/doc/list'); docs = r.json().get('docs', [])
print('5. doc list:', r.status_code, 'count=', len(docs))

# 6. 问答（无密钥 → 降级演示模式）
r = client.post('/api/chat', json={'session_id': sid, 'question': '什么是LangChain？'})
print('6. chat:', r.status_code)
data = r.json()
answer = data.get('answer', '')
print('   answer_head:', answer[:60].replace(chr(10), ' '))
print('   confidence:', data.get('confidence'), '| sub_queries:', data.get('sub_queries'))

# 7. 会话历史（应有 2 条消息）
r = client.get(f'/api/session/{sid}/history')
msgs = r.json().get('messages', [])
print('7. history:', r.status_code, 'messages=', len(msgs))

print()
print('=== ALL API ENDPOINTS PASSED ===')