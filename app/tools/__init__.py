"""LangChain Tools.

包含两类工具:
  - 本地农业工具（知识库、天气、农历、市场和时间）
  - MCP 工具（天气、联网搜索等）：通过 mcp_client_manager 远程加载

调用方请直接 from app.tools.<module> import ..., 本包不做 re-export,
避免在 import 包时触发 mcp_loader 等模块的连接副作用。
"""
