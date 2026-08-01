"""农业 MCP 工具服务（独立进程）。

每个文件是一个独立的 MCP server, 通过 streamable-http transport 暴露工具.
被 AgroAgentOS 主应用通过 langchain_mcp_adapters 远程调用。

当前保留天气与受限农业联网搜索服务；具体启动方式以项目配置和启动脚本为准。
"""
