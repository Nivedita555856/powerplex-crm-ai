"""
crewai_agents.py — CrewAI multi-agent recommendation crew.
Crew: Market Analyst + Product Expert → Recommendation Synthesiser.
Gracefully skips if crewai not installed.
"""
from typing import Optional

try:
    from crewai import Agent, Task, Crew, Process
    _CREWAI = True
except ImportError:
    _CREWAI = False


def crewai_available() -> bool:
    return _CREWAI


def run_recommendation_crew(customer_profile: str, query: str,
                             appliances_ctx: str, groq_api_key: str,
                             llm_model: str = "groq/llama3-70b-8192") -> Optional[str]:
    """
    Run a 3-agent CrewAI crew:
      1. Market Analyst   — analyses customer profile & needs
      2. Product Expert   — maps needs to available appliances
      3. Recommendation Writer — synthesises a concise recommendation
    Returns the final recommendation text, or None if crewai unavailable.
    """
    if not _CREWAI:
        return None
    if not groq_api_key:
        return None

    try:
        from crewai import LLM
        llm = LLM(
            model=llm_model,
            api_key=groq_api_key,
            base_url="https://api.groq.com/openai/v1",
            max_tokens=350,
            temperature=0.4,
        )

        market_analyst = Agent(
            role="Customer Needs Analyst",
            goal="Understand the customer's requirements from their profile and query",
            backstory=(
                "You are an expert at understanding consumer appliance needs. "
                "You analyse customer segments, history, and stated requirements."
            ),
            llm=llm,
            verbose=False,
            max_iter=2,
        )
        product_expert = Agent(
            role="Appliance Product Expert",
            goal="Match customer needs to the best available appliances",
            backstory=(
                "You are an expert on home appliances — AC, refrigerator, washing machine, "
                "microwave, television brands and models. You recommend based on value and fit."
            ),
            llm=llm,
            verbose=False,
            max_iter=2,
        )

        analyse_task = Task(
            description=(
                f"Customer profile:\n{customer_profile}\n\n"
                f"Customer query: {query}\n\n"
                "Identify the top 2-3 needs/priorities of this customer."
            ),
            expected_output="Bullet list of customer needs (max 3 points).",
            agent=market_analyst,
        )
        recommend_task = Task(
            description=(
                f"Available products:\n{appliances_ctx}\n\n"
                "Based on the identified customer needs, recommend the best 2 appliances. "
                "Include product name, why it fits, and price if available."
            ),
            expected_output="2-appliance recommendation with rationale (max 5 sentences).",
            agent=product_expert,
            context=[analyse_task],
        )

        crew = Crew(
            agents=[market_analyst, product_expert],
            tasks=[analyse_task, recommend_task],
            process=Process.sequential,
            verbose=False,
        )
        result = crew.kickoff()
        return str(result) if result else None

    except Exception as e:
        print(f"[CrewAI] Error: {e}")
        return None
