import json
from typing import Dict, Any, Optional

from ..llm.bailian_client import bailian_client


class ActionPlanner:
    """将自然语言动作映射到 agent-browser snapshot ref 命令"""

    SYSTEM_PROMPT = """你是一个浏览器自动化专家。你的任务是根据页面无障碍树快照和要执行的操作，
确定应该对哪个元素执行什么命令。

页面快照使用 @eN 形式的引用标识每个可交互元素，例如：
  @e1 textbox "用户名"
  @e2 textbox "密码"
  @e3 button "登录"

你需要返回一个 JSON 对象，包含以下字段：
- command: 要执行的命令类型，取值为 "click", "fill", "wait", "screenshot", "scroll", "verify"
- ref: 目标元素的引用 (如 "@e3")，verify/wait/screenshot/scroll 类型可为空字符串
- value: fill 命令时需要填写的文本值，其他命令为空字符串
- element_name: 目标元素在快照中显示的名称（引号内的文字，如 "用户名"、"登录"）
- element_role: 目标元素的角色类型 (textbox, button, link, checkbox 等)
- reasoning: 你的推理过程（简短说明为什么选择这个元素）

只输出 JSON，不要添加其他内容。"""

    async def plan_action(
        self,
        action: str,
        snapshot_text: str,
        previous_actions: str = "",
        default_username: str = "",
        default_password: str = "",
    ) -> Dict[str, Any]:
        """
        根据页面快照和动作描述，规划 agent-browser 命令
        Args:
            action: 要执行的操作描述（自然语言）
            snapshot_text: 页面无障碍树快照文本
            previous_actions: 已执行的操作记录
            default_username: 默认用户名
            default_password: 默认密码
        Returns:
            {"command": str, "ref": str, "value": str, "reasoning": str}
        """
        context_hint = ""
        if default_username or default_password:
            context_hint = f"\n可用的测试数据：用户名={default_username}，密码={default_password}"

        previous_hint = ""
        if previous_actions:
            previous_hint = f"\n已执行的操作：\n{previous_actions}"

        prompt = f"""当前页面无障碍树快照：
{snapshot_text}
{context_hint}
{previous_hint}

要执行的操作：{action}

请返回一个JSON对象，指定应该执行的命令。只输出JSON，不要添加其他内容。"""

        try:
            response = await bailian_client.generate_text(prompt, self.SYSTEM_PROMPT)

            # 清理响应文本
            response = response.strip()
            if response.startswith("```"):
                # 去除 markdown 代码块
                lines = response.split("\n")
                lines = [l for l in lines if not l.startswith("```")]
                response = "\n".join(lines).strip()

            result = json.loads(response)

            # 验证必要字段
            if "command" not in result:
                result["command"] = "click"
            if "ref" not in result:
                result["ref"] = ""
            if "value" not in result:
                result["value"] = ""
            if "element_name" not in result:
                result["element_name"] = ""
            if "element_role" not in result:
                result["element_role"] = ""
            if "reasoning" not in result:
                result["reasoning"] = ""

            print(f"[ActionPlanner] action={action} -> command={result['command']} ref={result['ref']} value={result.get('value', '')} element_name={result.get('element_name', '')} element_role={result.get('element_role', '')}")
            return result

        except json.JSONDecodeError as e:
            print(f"[ActionPlanner] JSON 解析失败: {e}, response={response}")
            return {
                "command": "click",
                "ref": "",
                "value": "",
                "element_name": "",
                "element_role": "",
                "reasoning": f"JSON 解析失败: {e}",
                "error": True,
            }
        except Exception as e:
            print(f"[ActionPlanner] 错误: {e}")
            return {
                "command": "click",
                "ref": "",
                "value": "",
                "element_name": "",
                "element_role": "",
                "reasoning": str(e),
                "error": True,
            }
