import json

from harbor.agents.base import BaseAgent
from harbor.models.trajectories.trajectory import Trajectory


class ScriptedHelloAgent(BaseAgent):
    @staticmethod
    def name():
        return "scripted-hello"

    def version(self):
        return "1.0.0"

    async def setup(self, environment):
        pass

    async def run(self, instruction, environment, context):
        steps = [{"step_id": 1, "source": "user", "message": instruction}]
        for index, (call_id, command) in enumerate((
            ("write", "printf '%s\\n' 'Hello, world!' > /app/hello.txt"),
            ("read", "cat /app/hello.txt"),
        ), start=2):
            result = await environment.exec(command=command)
            steps.append({
                "step_id": index, "source": "agent", "message": "", "llm_call_count": 0,
                "tool_calls": [{"tool_call_id": call_id, "function_name": "shell", "arguments": {"command": command}}],
                "observation": {"results": [{
                    "source_call_id": call_id, "content": result.stdout,
                    "extra": {"return_code": result.return_code},
                }]},
            })
        steps.append({"step_id": 4, "source": "agent", "message": "Created hello.txt.", "llm_call_count": 0})
        trajectory = Trajectory(agent={"name": self.name(), "version": self.version()}, steps=steps)
        (self.logs_dir / "trajectory.json").write_text(json.dumps(trajectory.to_json_dict(), indent=2), encoding="utf-8")
