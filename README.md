# Intelligent-Knowledge-Base-Assistant
企业智能知识库助手是一套面向中小企业的内部资料问答系统。员工的制度、产品资料、销售文档散落在 PDF/Word/Excel 与共享盘中，找一条答案平均要问三个人、花二十分钟。系统把资料解析、切片并向量化入库，员工用自然语言提问即可获得带原文出处的回答，避免模型编造；当问题需要真实业务数据时，系统再调用工具查询数据库并生成报表。技术栈为 FastAPI + PostgreSQL(pgvector) + RAG/Agent，Docker 化后部署于云主机，接口由 pytest 覆盖，日志与成本可控。
