"""
Agent-Browser CLI 工具类（同步版本）
供生成的测试脚本在运行时 import 调用，通过 subprocess 调用 agent-browser CLI。
"""

import base64
import json
import os
import re
import subprocess
import threading
import time
import uuid
from typing import Dict, Any, Optional, List


class AgentBrowserUtil:
    """同步 agent-browser CLI 工具类"""

    def __init__(self, session_id: str = None, profile_path: str = None):
        self.session_id = session_id or uuid.uuid4().hex[:8]
        self.profile_path = profile_path

    def _run_cli(self, args: List[str], timeout: int = 30) -> Dict[str, Any]:
        """
        同步执行 agent-browser CLI，逐行读 stdout 寻找 JSON。
        使用 subprocess.Popen + 后台线程读 stdout（解决浏览器子进程管道继承问题）。
        """
        cmd = ["agent-browser", "--session", self.session_id]
        if self.profile_path:
            cmd.extend(["--profile", self.profile_path])
        cmd.extend(args + ["--json"])
        cmd_str = " ".join(cmd)
        print(f"[AgentBrowserUtil] 执行: {cmd_str}")

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            print("[AgentBrowserUtil] agent-browser 未安装")
            return {
                "success": False,
                "error": "agent-browser 未安装。请运行: npm install -g @anthropic-ai/agent-browser && agent-browser install",
            }

        json_result = None
        collected_lines = []

        def read_stdout():
            nonlocal json_result
            for raw_line in iter(process.stdout.readline, b""):
                decoded = raw_line.decode("utf-8", errors="replace").strip()
                if not decoded:
                    continue
                collected_lines.append(decoded)
                try:
                    json_result = json.loads(decoded)
                    break
                except json.JSONDecodeError:
                    continue

        reader = threading.Thread(target=read_stdout, daemon=True)
        reader.start()
        reader.join(timeout=timeout)

        if reader.is_alive():
            # 超时
            print(f"[AgentBrowserUtil] 超时: {cmd_str}")
            try:
                process.kill()
            except Exception:
                pass
            return {"success": False, "error": f"命令超时 ({timeout}s)"}

        # 等待进程退出（确保操作在浏览器中完全完成）
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            # 进程未退出但 JSON 已拿到，继续处理
            try:
                process.kill()
            except Exception:
                pass

        # 读取 stderr
        stderr_data = b""
        try:
            stderr_data = process.stderr.read()
        except Exception:
            pass
        if stderr_data:
            stderr_text = stderr_data.decode("utf-8", errors="replace").strip()
            if stderr_text:
                print(f"[AgentBrowserUtil] stderr: {stderr_text[:500]}")

        if json_result is not None:
            result = json_result
        elif collected_lines:
            full_text = "\n".join(collected_lines)
            try:
                result = json.loads(full_text)
            except json.JSONDecodeError:
                result = {"success": True, "raw_output": full_text}
        else:
            result = {"success": True}

        result_str = json.dumps(result, ensure_ascii=False)
        if len(result_str) > 2000:
            print(f"[AgentBrowserUtil] 返回: {result_str[:500]}... (共 {len(result_str)} 字符)")
        else:
            print(f"[AgentBrowserUtil] 返回: {result_str}")

        return result

    # ---- 基础 CLI 封装 ----

    def open(self, url: str, headless: bool = True) -> Dict[str, Any]:
        """打开浏览器并导航到 URL"""
        args = ["open", url]
        if not headless:
            args.append("--headed")
        return self._run_cli(args, timeout=60)

    def set_viewport(self, width: int = 1920, height: int = 1080) -> Dict[str, Any]:
        """设置浏览器视口大小"""
        return self._run_cli(["set", "viewport", str(width), str(height)], timeout=10)

    def press_key(self, key: str) -> Dict[str, Any]:
        """按下键盘按键，如 Escape, Enter, Tab, ArrowDown 等"""
        return self._run_cli(["press", key], timeout=10)

    def select_option(self, ref: str, value: str) -> Dict[str, Any]:
        """选择下拉框选项（仅适用于原生 <select> 元素）"""
        return self._run_cli(["select", ref, value], timeout=15)

    def snapshot(self, interactive: bool = True) -> Dict[str, Any]:
        """获取页面无障碍树快照"""
        args = ["snapshot"]
        if interactive:
            args.append("-i")
        return self._run_cli(args, timeout=30)

    def click(self, ref: str) -> Dict[str, Any]:
        """点击指定 ref 元素"""
        return self._run_cli(["click", ref], timeout=30)

    def fill(self, ref: str, value: str) -> Dict[str, Any]:
        """在指定 ref 元素中填写文本"""
        return self._run_cli(["fill", ref, value], timeout=30)

    def screenshot(self, path: Optional[str] = None) -> Dict[str, Any]:
        """截取页面截图。path 是位置参数，非 --output"""
        args = ["screenshot"]
        if path:
            args.append(path)
        return self._run_cli(args, timeout=30)

    def wait(self, ms: int) -> Dict[str, Any]:
        """等待指定毫秒"""
        return self._run_cli(["wait", str(ms)], timeout=max(ms // 1000 + 10, 15))

    def cookies_get(self) -> Dict[str, Any]:
        """获取所有 cookies"""
        return self._run_cli(["cookies", "get"], timeout=10)

    def cookies_set(self, name: str, value: str, domain: str = "") -> Dict[str, Any]:
        """设置 cookie"""
        args = ["cookies", "set", name, value]
        if domain:
            args.extend(["--domain", domain])
        return self._run_cli(args, timeout=10)

    def close(self) -> Dict[str, Any]:
        """关闭浏览器会话"""
        return self._run_cli(["close"], timeout=15)

    # ---- 智能操作（snapshot + 元素查找 + 执行） ----

    def _extract_snapshot_text(self, snap_result: Dict[str, Any]) -> str:
        """从 snapshot CLI 返回结果中提取 snapshot 文本"""
        # agent-browser 返回格式: {"success": true, "data": {"snapshot": "..."}, "error": null}
        data = snap_result.get("data", {})
        if isinstance(data, dict):
            text = data.get("snapshot", "")
            if text:
                return text
        # 兼容旧格式（直接在顶层）
        text = snap_result.get("snapshot", "")
        if text:
            return text
        return snap_result.get("raw_output", "")

    def find_element_in_snapshot(
        self,
        snapshot_text: str,
        name: Optional[str] = None,
        role: Optional[str] = None,
    ) -> Optional[str]:
        """
        在 snapshot 文本中按 name/role 匹配元素，返回 @eN ref。
        agent-browser snapshot 格式:
          - textbox "请输入用户名" [ref=e2]
          - button "登 录" [ref=e7]
          - button [ref=e1]
        """
        if not snapshot_text or not name:
            return None

        # 正则匹配 agent-browser snapshot 行: role "name" [ref=eN]
        # 格式: - role "name" [ref=eN]  或  - role [ref=eN] (无名称)
        pattern = r'(\w+)\s+"([^"]*)"\s+\[ref=(e\d+)\]'
        matches = re.findall(pattern, snapshot_text)

        # 按 role 过滤（如果指定）
        candidates = []
        for elem_role, elem_name, ref_id in matches:
            ref = f"@{ref_id}"
            if role and elem_role.lower() != role.lower():
                continue
            candidates.append((ref, elem_role, elem_name))

        # 如果按 role 过滤后无结果，放宽不过滤 role
        if not candidates and role:
            candidates = [(f"@{ref_id}", r, n) for r, n, ref_id in matches]

        # 1. 精确匹配
        for ref, elem_role, elem_name in candidates:
            if elem_name == name:
                return ref

        # 2. 忽略大小写精确匹配
        name_lower = name.lower()
        for ref, elem_role, elem_name in candidates:
            if elem_name.lower() == name_lower:
                return ref

        # 3. 去除空格后精确匹配（处理 "登 录" vs "登录"）
        name_stripped = name_lower.replace(" ", "")
        for ref, elem_role, elem_name in candidates:
            if elem_name.lower().replace(" ", "") == name_stripped:
                return ref

        # 4. 模糊匹配（包含关系，去除空格）
        for ref, elem_role, elem_name in candidates:
            elem_stripped = elem_name.lower().replace(" ", "")
            if name_stripped in elem_stripped or elem_stripped in name_stripped:
                return ref

        return None

    def smart_click(self, element_text: str, element_role: Optional[str] = None) -> Dict[str, Any]:
        """snapshot → 按 name/role 找 ref → click"""
        snap = self.snapshot()
        snapshot_text = self._extract_snapshot_text(snap)
        if not snapshot_text:
            print(f"[AgentBrowserUtil] smart_click: snapshot 返回空，snap={snap}")
        ref = self.find_element_in_snapshot(snapshot_text, name=element_text, role=element_role)
        if not ref:
            print(f"[AgentBrowserUtil] smart_click: 未找到元素 text={element_text} role={element_role}")
            print(f"[AgentBrowserUtil] snapshot 内容:\n{snapshot_text[:1000]}")
            raise RuntimeError(f"未找到元素: text={element_text}, role={element_role}")
        print(f"[AgentBrowserUtil] smart_click: 找到 {ref} -> click")
        return self.click(ref)

    def smart_fill(self, element_text: str, value: str, element_role: Optional[str] = None) -> Dict[str, Any]:
        """snapshot → 按 name/role 找 ref → fill"""
        snap = self.snapshot()
        snapshot_text = self._extract_snapshot_text(snap)
        if not snapshot_text:
            print(f"[AgentBrowserUtil] smart_fill: snapshot 返回空，snap={snap}")
        ref = self.find_element_in_snapshot(snapshot_text, name=element_text, role=element_role)
        if not ref:
            print(f"[AgentBrowserUtil] smart_fill: 未找到元素 text={element_text} role={element_role}")
            print(f"[AgentBrowserUtil] snapshot 内容:\n{snapshot_text[:1000]}")
            raise RuntimeError(f"未找到元素: text={element_text}, role={element_role}")
        print(f"[AgentBrowserUtil] smart_fill: 找到 {ref} -> fill '{value}'")
        return self.fill(ref, value)

    def load_cookies(self, cookies_file_path: str) -> None:
        """从 JSON 文件加载 cookies"""
        if not os.path.exists(cookies_file_path):
            print(f"[AgentBrowserUtil] Cookies 文件不存在: {cookies_file_path}")
            return
        with open(cookies_file_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        for c in cookies:
            name = c.get("name", "")
            value = c.get("value", "")
            domain = c.get("domain", "")
            if name and value:
                self.cookies_set(name, value, domain=domain)
        print(f"[AgentBrowserUtil] 已加载 {len(cookies)} 个 cookies")

    def save_cookies(self, cookies_file_path: str) -> None:
        """保存 cookies 到 JSON 文件"""
        result = self.cookies_get()
        # agent-browser 返回格式: {"data": {"cookies": [...]}} 或旧格式 {"cookies": [...]}
        data = result.get("data", {})
        cookies = data.get("cookies", []) if isinstance(data, dict) else []
        if not cookies:
            cookies = result.get("cookies", [])
        os.makedirs(os.path.dirname(cookies_file_path) or ".", exist_ok=True)
        with open(cookies_file_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f"[AgentBrowserUtil] 已保存 {len(cookies)} 个 cookies")

    def detect_and_solve_captcha(self) -> bool:
        """
        截图 → VL 识别验证码文本 → snapshot 找输入框 → fill。
        流程:
          1. agent-browser screenshot <path> → 全页截图保存到本地
          2. base64 编码 → VL 模型直接识别验证码文本（一步完成检测+识别）
          3. agent-browser snapshot → 找到验证码输入框 ref
          4. agent-browser fill @ref <text> → 填入
        """
        try:
            from openai import OpenAI

            api_key = os.getenv("BAILIAN_API_KEY", "")
            base_url = os.getenv("BAILIAN_BASE_URL", "")
            vl_model = os.getenv("BAILIAN_VL_MODEL", "qwen-vl-plus")

            if not api_key or not base_url:
                print("[AgentBrowserUtil] 未配置 BAILIAN_API_KEY 或 BAILIAN_BASE_URL，跳过验证码检测")
                return False

            # 1. 截图（位置参数）
            captcha_temp_path = os.path.abspath(f"captcha_ab_{self.session_id}.png")
            ss_result = self.screenshot(path=captcha_temp_path)

            # 如果指定路径不存在，尝试从响应中读取实际保存路径
            actual_path = captcha_temp_path
            if not os.path.exists(actual_path):
                resp_path = ss_result.get("data", {}).get("path", "")
                if resp_path and os.path.exists(resp_path):
                    actual_path = resp_path
                    print(f"[AgentBrowserUtil] 使用响应路径: {actual_path}")
                else:
                    print(f"[AgentBrowserUtil] 截图文件不存在: {captcha_temp_path}, 响应: {ss_result}")
                    return False

            with open(actual_path, "rb") as f:
                screenshot_b64 = base64.b64encode(f.read()).decode("utf-8")

            print(f"[AgentBrowserUtil] 截图已保存: {actual_path} ({len(screenshot_b64)} bytes base64)")

            # 2. VL 一步识别验证码（检测+识别合并）
            client = OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=vl_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是一个验证码识别专家。分析网页截图，找到验证码图片并识别其内容。\n"
                            "如果是数学运算（如 2+3=?），请计算并返回结果数字。\n"
                            "如果是文字/数字验证码，直接返回验证码文本。\n"
                            "如果没有发现验证码，返回 NONE。\n"
                            "只返回验证码值或 NONE，不要添加任何解释。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "请识别这张网页截图中的验证码内容。只返回验证码的值（数字或文字），如果没有验证码返回NONE。"},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
                        ],
                    },
                ],
                temperature=0.0,
                max_tokens=50,
            )
            captcha_text_raw = response.choices[0].message.content.strip()
            print(f"[AgentBrowserUtil] VL 识别结果(原始): {captcha_text_raw}")

            # 检查是否有验证码
            if captcha_text_raw.upper() == "NONE" or not captcha_text_raw:
                print("[AgentBrowserUtil] VL 未检测到验证码")
                self._cleanup_temp(actual_path)
                return False

            # 提取数字/文本
            captcha_text = captcha_text_raw
            match = re.search(r"[=:]\s*(\d+)", captcha_text_raw)
            if match:
                captcha_text = match.group(1)
            elif captcha_text_raw.isdigit():
                captcha_text = captcha_text_raw
            else:
                numbers = re.findall(r"\d+", captcha_text_raw)
                if numbers:
                    captcha_text = numbers[-1]

            print(f"[AgentBrowserUtil] 提取后的验证码: {captcha_text}")

            # 3. snapshot 找验证码输入框 → fill
            snap = self.snapshot()
            snapshot_text = self._extract_snapshot_text(snap)
            # 尝试多种名称匹配验证码输入框
            captcha_names = ["验证码", "captcha", "code", "verify"]
            ref = None
            for cname in captcha_names:
                ref = self.find_element_in_snapshot(snapshot_text, name=cname, role="textbox")
                if ref:
                    break
            if not ref:
                # 宽松搜索：不限 role
                for cname in captcha_names:
                    ref = self.find_element_in_snapshot(snapshot_text, name=cname)
                    if ref:
                        break

            if ref:
                self.fill(ref, captcha_text)
                print(f"[AgentBrowserUtil] 验证码已填写: {captcha_text} -> {ref}")
                self._cleanup_temp(actual_path)
                return True
            else:
                print(f"[AgentBrowserUtil] 未找到验证码输入框, snapshot:\n{snapshot_text[:500]}")
                self._cleanup_temp(actual_path)
                return False

        except Exception as e:
            print(f"[AgentBrowserUtil] 验证码处理失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _cleanup_temp(self, path: str) -> None:
        """清理临时文件"""
        try:
            if os.path.exists(path):
                os.unlink(path)
        except Exception:
            pass

    def verify_step_screenshots(self, step_screenshots: list) -> list:
        """
        批量调用 VL 模型验证每个步骤的截图是否执行成功。
        Args:
            step_screenshots: [{"step_number": 1, "step_name": "输入用户名", "screenshot_path": "..."}]
        Returns:
            [{"step_number": 1, "verified": True/False, "reason": "..."}]
        """
        try:
            from openai import OpenAI

            api_key = os.getenv("BAILIAN_API_KEY", "")
            base_url = os.getenv("BAILIAN_BASE_URL", "")
            vl_model = os.getenv("BAILIAN_VL_MODEL", "qwen-vl-plus")

            if not api_key or not base_url:
                print("[AgentBrowserUtil] 未配置 BAILIAN_API_KEY 或 BAILIAN_BASE_URL，跳过VL验证")
                return []

            client = OpenAI(api_key=api_key, base_url=base_url)
            results = []

            for step_info in step_screenshots:
                step_number = step_info["step_number"]
                step_name = step_info["step_name"]
                screenshot_path = step_info["screenshot_path"]

                if not os.path.exists(screenshot_path):
                    print(f"[AgentBrowserUtil] 截图文件不存在，跳过: {screenshot_path}")
                    results.append({
                        "step_number": step_number,
                        "verified": False,
                        "reason": "截图文件不存在"
                    })
                    continue

                try:
                    with open(screenshot_path, "rb") as f:
                        screenshot_b64 = base64.b64encode(f.read()).decode("utf-8")

                    response = client.chat.completions.create(
                        model=vl_model,
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "你是一个网页测试验证专家。你需要根据网页截图判断某个操作步骤是否执行成功。\n"
                                    "只返回 SUCCESS 或 FAILED，后跟一个简短的原因（不超过30字）。\n"
                                    "格式：SUCCESS: 原因 或 FAILED: 原因"
                                ),
                            },
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": f"这是执行'{step_name}'之后的网页截图，请判断该操作是否执行成功。"
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}
                                    },
                                ],
                            },
                        ],
                        temperature=0.0,
                        max_tokens=100,
                    )
                    vl_response = response.choices[0].message.content.strip()
                    print(f"[AgentBrowserUtil] VL验证 step {step_number}: {vl_response}")

                    verified = vl_response.upper().startswith("SUCCESS")
                    reason = vl_response.split(":", 1)[1].strip() if ":" in vl_response else vl_response
                    results.append({
                        "step_number": step_number,
                        "verified": verified,
                        "reason": reason
                    })

                except Exception as e:
                    print(f"[AgentBrowserUtil] VL验证 step {step_number} 失败: {e}")
                    results.append({
                        "step_number": step_number,
                        "verified": False,
                        "reason": f"VL验证调用失败: {str(e)}"
                    })

            return results

        except Exception as e:
            print(f"[AgentBrowserUtil] VL批量验证失败: {e}")
            return []
