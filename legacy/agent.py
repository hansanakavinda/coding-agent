from dotenv import load_dotenv
import os

from tools import write_py_file

load_dotenv()

SYSTEM_PROMPT = """
Your are an expert Python developer

You have access to the following tools,

- write_py_file: allow you to write string into a python file.

once the task is completed return the summary of the work did.

"""

from langchain_openrouter import ChatOpenRouter

model = ChatOpenRouter(
    model="nvidia/nemotron-3-super-120b-a12b:free",
    temperature=0,
    max_tokens=4096,
    max_retries=2
)

from dataclasses import dataclass

# We use a dataclass here, but Pydantic models are also supported.
@dataclass
class ResponseFormat:
    """Response schema for the agent."""
    
    summary: str

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

agent = create_agent(
    model=model,
    tools=[write_py_file],
    system_prompt=SYSTEM_PROMPT,
    response_format=ToolStrategy(ResponseFormat),
)

prompt = "generate a function to evaluate python code against user query and return feedback using an llm as judge. use langchain with openrouter api to build the function."

try:
    response = agent.invoke(
        {"messages": [{"role": "user", "content": prompt}]},
    )
except Exception as e:
    response = f"Error: {e}"

print(response)

