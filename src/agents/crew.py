"""
CrewAI Crew 정의 및 실행 진입점
"""
import os

from crewai import Crew, Task
from dotenv import load_dotenv

from src.agents.prompts import ADVISOR_TASK, RESEARCHER_TASK
from src.agents.roles import build_tax_advisor, build_tax_researcher

load_dotenv()

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-7")


def _build_llm():
    """CrewAI용 LLM 객체 반환 (Claude)"""
    from crewai import LLM
    return LLM(
        model=f"anthropic/{CLAUDE_MODEL}",
        api_key=os.getenv("ANTHROPIC_API_KEY"),
    )


def run_tax_crew(question: str) -> str:
    """
    양도소득세 질문을 2-agent CrewAI로 처리.
    반환값: 최종 답변 문자열
    """
    llm = _build_llm()

    researcher = build_tax_researcher(llm)
    advisor = build_tax_advisor(llm)

    research_task = Task(
        description=RESEARCHER_TASK.format(question=question),
        expected_output="검색된 법령 조문 목록 (chunk_id 포함)",
        agent=researcher,
    )

    advice_task = Task(
        description=ADVISOR_TASK.format(
            question=question,
            research_result="{research_task_output}",
        ),
        expected_output="[요약 판단] / [근거 법령] / [판단 과정] / [추가 확인 필요] / [유의사항] 형식의 한국어 답변",
        agent=advisor,
        context=[research_task],
    )

    crew = Crew(
        agents=[researcher, advisor],
        tasks=[research_task, advice_task],
        verbose=True,
    )

    result = crew.kickoff()
    return str(result)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    question = "2년 보유한 1세대 1주택을 양도하면 비과세가 되나요?"
    print(f"질문: {question}\n")
    answer = run_tax_crew(question)
    print("\n=== 최종 답변 ===")
    print(answer)
