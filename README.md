# QQMusic MCP (uv 管理的工具集)

A uv-managed collection of QQ Music MCP tools for searching lyrics, resolving playback URLs, and exposing playlist/comment/lyric metadata to AI clients.

一个通过 `uv` 管理依赖的 QQ 音乐 MCP 工具合集，帮助 AI 客户端搜索歌词、解析播放链接并获取歌单、评论和歌词信息。

## Overview | 概述

`qqmusic_mcp.py` 基于 `FastMCP` 构建 manifest，暴露 `search_music_by_lyrics` 与 `get_music_url_by_songmid` 两个工具。`qqmusic_service.py` 负责读取 `QQM_COOKIE`、注入 `qqmusic_client` 并提供服务层，而 `qqmusic_client.py` 则实现全部 HTTP 请求与 JavaScript 签名逻辑。借助 `uv.lock` 与 `pyproject.toml` 能确保依赖可重复安装。

`qqmusic_mcp.py` builds a `FastMCP` manifest with two tools (`search_music_by_lyrics` and `get_music_url_by_songmid`), `qqmusic_service.py` bootstraps the QQ Music client using `qqmusic_client.py`, and the provided `uv.lock`/`pyproject.toml` make the dependency graph reproducible.

## uv Workflow | uv 工作流程

1. Install `uv` if you do not already have it (e.g., `pip install uv`).
   如果尚未安装 `uv`，可以通过 `pip install uv` 获取，并确保可以在项目目录运行。
2. Sync dependencies into the managed virtual environment:

   ```bash
   uv sync
   ```

3. Provide your QQ Music cookie so the service can authenticate (`QQM_COOKIE` can be exported or stored in `.env`, see `.env.example`).

   ```bash
   export QQM_COOKIE="<your_cookie>"
   ```

4. Start the QQ Music MCP manifest using the managed interpreter:

   ```bash
   uv run python qqmusic_mcp.py
   ```

5. (Optional) Use `mcp_pipe.py` to connect a client to the manifest, again via `uv run`:

   ```bash
   uv run python mcp_pipe.py qqmusic_mcp.py
   ```

   This keeps every component running inside the same `uv`-managed environment so the `uv.lock` dependency set is honored.

## Project Structure | 项目结构

- `qqmusic_client.py`: QQ 音乐 HTTP 接口与 `execjs` 签名逻辑，构成最底层的 API 套件
- `qqmusic_service.py`: 加载 `.env`/`QQM_COOKIE` 并构建 `QQMusic` helper，以便 MCP manifest 使用
- `qqmusic_mcp.py`: FastMCP manifest，定义两个对外工具供 AI 调用
- `mcp_pipe.py`: 通用 MCP 管道，可通过 stdio/SSE/HTTP 连接工具
- `uv.lock` + `pyproject.toml`: 依赖描述与锁定，通过 `uv sync` 控制
- `loader.js`, `main.js`, `module.js`, `ventor.js`: Web 签名/加载器辅助脚本

## Configuration Hints | 配置说明

- `QQM_COOKIE`：要么导出环境变量，要么写入 `.env`（推荐参考 `.env.example`）
- `uv run --managed-python`：在多个系统共存 Python 版本时强制使用 `uv` 管理的解释器
- `mcp_config.json`: 如需将 `qqmusic_mcp` 与其他工具桥接，可新增条目并通过 `mcp_pipe.py` 加载

## Recommendations | 建议

- Always run commands through `uv run` so the `.venv` created by `uv sync` is used consistently.
- Use `uv export --format=requirements.txt` if you need a legacy `requirements.txt` view of the resolved dependencies.

## Contributing | 贡献指南

欢迎提交 PR，请在 `uv sync` 后通过 `uv run` 运行相关脚本以验证你的改动。

Contributions are welcome! Make sure to run the relevant scripts via `uv run` after `uv sync` to verify changes.

## Acknowledgments | 致谢

Thanks to https://github.com/ZWD11/QQmusicApi for the detailed QQ Music API reverse engineering that inspired this project.

## License | 许可证

MIT License | MIT 许可证
