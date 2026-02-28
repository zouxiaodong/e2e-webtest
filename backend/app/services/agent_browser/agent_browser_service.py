import asyncio
import json
import logging
import uuid
import os
from typing import Dict, Any, List, Optional

logger = logging.getLogger("agent_browser")


class AgentBrowserService:
    """封装 agent-browser CLI 调用"""

    def __init__(self, session_id: Optional[str] = None, profile_path: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.profile_path = profile_path

    async def _run_cli(self, args: List[str], timeout: int = 30) -> Dict[str, Any]:
        """
        执行 agent-browser CLI 命令并返回 JSON 结果。
        采用逐行读取 stdout 的方式：一旦收到完整 JSON 就立即返回，
        不等待进程退出（因为浏览器子进程会继承管道导致 communicate() 永远阻塞）。
        """
        cmd = ["agent-browser", "--session", self.session_id]
        if self.profile_path:
            cmd.extend(["--profile", self.profile_path])
        cmd.extend(args + ["--json"])
        cmd_str = " ".join(cmd)
        logger.info(f"[CMD] >>> {cmd_str}")
        print(f"[AgentBrowser] 执行: {cmd_str}")

        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # 逐行读取 stdout，拿到 JSON 就返回（不等进程退出）
            collected_lines = []
            json_result = None

            async def read_stderr():
                """后台读 stderr"""
                lines = []
                while True:
                    line = await process.stderr.readline()
                    if not line:
                        break
                    lines.append(line.decode("utf-8", errors="replace").strip())
                return lines

            stderr_task = asyncio.create_task(read_stderr())

            try:
                while True:
                    line = await asyncio.wait_for(
                        process.stdout.readline(), timeout=timeout
                    )
                    if not line:
                        # EOF — 进程 stdout 关闭
                        break
                    decoded = line.decode("utf-8", errors="replace").strip()
                    if not decoded:
                        continue
                    collected_lines.append(decoded)

                    # 尝试解析为 JSON
                    try:
                        json_result = json.loads(decoded)
                        # 拿到 JSON 结果，立即返回
                        break
                    except json.JSONDecodeError:
                        continue
            except asyncio.TimeoutError:
                # 读取超时
                logger.error(f"[TIMEOUT] {cmd_str} ({timeout}s)")
                print(f"[AgentBrowser] 超时: {cmd_str}")
                # 杀掉进程
                try:
                    process.kill()
                except Exception:
                    pass
                return {"success": False, "error": f"命令超时 ({timeout}s)"}

            # 等 stderr 读完（给一小段时间）
            try:
                stderr_lines = await asyncio.wait_for(stderr_task, timeout=2)
            except asyncio.TimeoutError:
                stderr_task.cancel()
                stderr_lines = []

            stderr_text = "\n".join(stderr_lines).strip()
            if stderr_text:
                logger.warning(f"[STDERR] {stderr_text}")
                print(f"[AgentBrowser] stderr: {stderr_text}")

            # 构建返回结果
            if json_result is not None:
                result = json_result
            elif collected_lines:
                # 尝试把所有行拼起来解析
                full_text = "\n".join(collected_lines)
                try:
                    result = json.loads(full_text)
                except json.JSONDecodeError:
                    result = {"success": True, "raw_output": full_text}
            else:
                result = {"success": True}

            # 输出日志（snapshot 可能很长，截断显示）
            result_str = json.dumps(result, ensure_ascii=False)
            if len(result_str) > 2000:
                logger.info(f"[RESULT] <<< {result_str[:2000]}... (truncated, total {len(result_str)} chars)")
                print(f"[AgentBrowser] 返回: {result_str[:500]}... (共 {len(result_str)} 字符)")
            else:
                logger.info(f"[RESULT] <<< {result_str}")
                print(f"[AgentBrowser] 返回: {result_str}")

            return result

        except FileNotFoundError:
            logger.error(f"[NOT_FOUND] agent-browser 未安装")
            print(f"[AgentBrowser] 未安装 agent-browser")
            return {
                "success": False,
                "error": "agent-browser 未安装。请运行: npm install -g @anthropic-ai/agent-browser && agent-browser install",
            }
        except Exception as e:
            logger.error(f"[ERROR] {cmd_str}: {e}")
            print(f"[AgentBrowser] 异常: {e}")
            return {"success": False, "error": str(e)}

    async def check_installed(self) -> bool:
        """检查 agent-browser 是否已安装"""
        try:
            process = await asyncio.create_subprocess_exec(
                "agent-browser", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10)
            version = stdout.decode("utf-8", errors="replace").strip()
            print(f"[AgentBrowser] 版本: {version}")
            return process.returncode == 0
        except (FileNotFoundError, asyncio.TimeoutError):
            return False

    async def open(self, url: str, headless: bool = True) -> Dict[str, Any]:
        """打开浏览器并导航到 URL"""
        args = ["open", url]
        if not headless:
            args.append("--headed")
        return await self._run_cli(args, timeout=60)

    async def set_viewport(self, width: int = 1920, height: int = 1080) -> Dict[str, Any]:
        """设置浏览器视口大小"""
        return await self._run_cli(["set", "viewport", str(width), str(height)], timeout=10)

    async def snapshot(self, interactive: bool = True) -> Dict[str, Any]:
        """
        获取页面无障碍树快照
        Args:
            interactive: 只返回可交互元素
        Returns:
            {snapshot: str, refs: [...]}
        """
        args = ["snapshot"]
        if interactive:
            args.append("-i")
        return await self._run_cli(args, timeout=30)

    async def click(self, ref: str) -> Dict[str, Any]:
        """点击指定 ref 元素"""
        return await self._run_cli(["click", ref], timeout=30)

    async def fill(self, ref: str, value: str) -> Dict[str, Any]:
        """在指定 ref 元素中填写文本"""
        return await self._run_cli(["fill", ref, value], timeout=30)

    async def screenshot(self, path: Optional[str] = None, annotate: bool = False) -> Dict[str, Any]:
        """截取页面截图"""
        args = ["screenshot"]
        if path:
            args.extend(["--output", path])
        if annotate:
            args.append("--annotate")
        return await self._run_cli(args, timeout=30)

    async def wait(self, ms: int) -> Dict[str, Any]:
        """等待指定毫秒"""
        return await self._run_cli(["wait", str(ms)], timeout=max(ms // 1000 + 10, 15))

    async def get_url(self) -> Dict[str, Any]:
        """获取当前页面 URL"""
        return await self._run_cli(["url"], timeout=10)

    async def cookies_get(self) -> Dict[str, Any]:
        """获取所有 cookies"""
        return await self._run_cli(["cookies", "get"], timeout=10)

    async def cookies_set(self, name: str, value: str, domain: str = "", path: str = "/") -> Dict[str, Any]:
        """设置 cookie"""
        args = ["cookies", "set", name, value]
        if domain:
            args.extend(["--domain", domain])
        if path != "/":
            args.extend(["--path", path])
        return await self._run_cli(args, timeout=10)

    async def storage_local_get(self) -> Dict[str, Any]:
        """获取 localStorage"""
        return await self._run_cli(["storage", "local", "get"], timeout=10)

    async def state_save(self, name: str) -> Dict[str, Any]:
        """保存浏览器状态"""
        return await self._run_cli(["state", "save", name], timeout=15)

    async def state_load(self, name: str) -> Dict[str, Any]:
        """加载浏览器状态"""
        return await self._run_cli(["state", "load", name], timeout=15)

    async def close(self) -> Dict[str, Any]:
        """关闭浏览器会话"""
        return await self._run_cli(["close"], timeout=15)
