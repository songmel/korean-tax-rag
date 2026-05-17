"""
CrewAI Agent 역할 정의
"""
from crewai import Agent
from src.agents.prompts import (
    ADVISOR_BACKSTORY,
    ADVISOR_GOAL,
    ADVISOR_ROLE,
    RESEARCHER_BACKSTORY,
    RESEARCHER_GOAL,
    RESEARCHER_ROLE,
)
from src.agents.tools import RAGSearchTool


def build_tax_researcher(llm) -> Agent:
    return Agent(
        role=RESEARCHER_ROLE,
        goal=RESEARCHER_GOAL,
        backstory=RESEARCHER_BACKSTORY,
        tools=[RAGSearchTool()],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def build_tax_advisor(llm) -> Agent:
    return Agent(
        role=ADVISOR_ROLE,
        goal=ADVISOR_GOAL,
        backstory=ADVISOR_BACKSTORY,
        tools=[],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )
