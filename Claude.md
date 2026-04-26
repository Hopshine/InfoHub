1. 这是windows系统,不要使用linux命令
2. 一般性的问题，直接运行命令即可，不要询问用户
Add under a new ## External API Integration section near the top of CLAUDE.md\n\nWhen implementing external API integrations (Weibo, Zhihu, Baidu, Douyin, Feishu, etc.), always:
- Test API endpoints incrementally before full implementation
- Check for anti-scraping measures and rate limits early
- Verify response formats and encoding (especially brotli/gzip)
- Add proper error handling and fallback mechanisms
- Document working endpoints and headers in comments
Add under ## Python/Flask Development section\n\nFor Flask/Python web applications:
- Always verify the correct port and host configuration before starting
- Check database paths are absolute or properly resolved
- Test server startup with a simple curl/request before declaring success
- Remind user that dev servers should run in their terminal, not via Bash tool
Add under ## Debugging section\n\nWhen debugging network/webhook issues:
- Distinguish between code bugs vs external infrastructure problems (tunnels, firewalls, DNS)
- Test locally first, then with tunnel/proxy
- Check both client AND server logs for timeout root causes
- Recommend infrastructure alternatives (ngrok, WebSocket, polling) when external network is the blocker