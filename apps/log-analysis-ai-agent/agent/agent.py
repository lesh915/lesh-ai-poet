"""
agent/agent.py
OpenAI 기반 tool-calling ReAct 에이전트 생성 및 실행.
"""

import os

import pandas as pd
from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from agent.prompts import build_system_prompt
from agent.tools import create_tools

load_dotenv()


def create_agent(
    log_df: pd.DataFrame,
    template_df: pd.DataFrame,
    merged_df: pd.DataFrame,
    template_tree: str,
) -> AgentExecutor:
    """
    세 DataFrame과 template_tree를 받아 AgentExecutor를 생성한다.

    Args:
        log_df: 원본 로그 테이블
        template_df: 고유 템플릿 테이블
        merged_df: 로그 + 템플릿 통합 테이블
        template_tree: Drain3 print_tree() 문자열

    Returns:
        실행 준비된 AgentExecutor
    """
    tools = create_tools(log_df, template_df, merged_df)

    system_prompt = build_system_prompt(
        log_columns=log_df.columns.tolist(),
        template_columns=template_df.columns.tolist(),
        merged_columns=merged_df.columns.tolist(),
        template_tree=template_tree,
    )

    llm = ChatOpenAI(
        model=os.getenv("AGENT_MODEL", "gpt-4o"),
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0,
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_openai_tools_agent(llm=llm, tools=tools, prompt=prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=10)


def run_query(agent_executor: AgentExecutor, query: str) -> str:
    """
    에이전트에 자연어 질의를 실행하고 응답 문자열을 반환한다.

    Args:
        agent_executor: create_agent()로 생성한 AgentExecutor
        query: 사용자 자연어 질의

    Returns:
        에이전트 응답 문자열
    """
    result = agent_executor.invoke({"input": query})
    return result["output"]
