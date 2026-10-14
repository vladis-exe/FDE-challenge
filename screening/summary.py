"""The recruiter note written when a screening ends (smart tier)."""

import json

from screening.llm import LLMClient, LLMResult
from screening.prompts import load_prompt
from screening.record import final_record
from screening.schemas import ConversationState
from screening.understand import render_transcript

SUMMARY_MAX_TOKENS = 400


def summarize(state: ConversationState, *, job_title: str, llm: LLMClient) -> LLMResult[str]:
    """Raises LLMError; the engine then stores no summary and logs llm_error."""
    record = {key: value for key, value in final_record(state).items() if key != "summary"}
    content = (
        f"<job>{job_title}</job>\n"
        f"<record>\n{json.dumps(record, ensure_ascii=False, indent=2)}\n</record>\n"
        f"<conversation>\n{render_transcript(state.transcript_tail)}\n</conversation>"
    )
    return llm.text(
        purpose="summary",
        system=load_prompt("summary"),
        messages=[{"role": "user", "content": content}],
        tier="smart",
        max_tokens=SUMMARY_MAX_TOKENS,
    )
