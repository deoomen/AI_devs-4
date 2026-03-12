from fastapi import FastAPI
from missions.mission03.proxy_agent import ProxyAgent, OperatorMessage, AgentMessage


app = FastAPI(
    title="AI_Devs 4 - Mission 03 - PROXY",
    version="1.0.0",
    openapi_url=None,
)
agent = ProxyAgent()

@app.get("/", summary="Home page")
def home():
    return {"message": "Hello Agent 5!"}

@app.post("/proxy-agent")
async def proxy_agent_endpoint(input: OperatorMessage) -> AgentMessage:
    return await agent.handle_message(input)
