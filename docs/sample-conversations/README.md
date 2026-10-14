# Sample conversations

Real transcripts from the eval suite: a simulated candidate (Sonnet 5.5 playing a persona) against the production engine, unedited. Each opens with what makes the case hard and what to notice. Times are the candidate's local time on the eval's fake clock.

Source run: `20261014-134341-v4-haiku`. Regenerate with `uv run python -m evals.samples <run dir>`.

| Sample | Shows |
| --- | --- |
| [Spain: every answer in one message](01-spain-everything-in-one-message.md) | A Spanish happy path where the candidate answers all seven questions in her first reply. |
| [English: a British candidate in Valencia](02-english-speaker-in-valencia.md) | An English-speaking candidate, screened entirely in English. |
| [Mexico: Spanglish, a side question and a burst of messages](03-spanglish-and-message-bursts.md) | A Monterrey candidate who mixes Spanish and English and sends three messages in a row before Alex can answer. |
| [Disqualified: a prompt injection, then no license](04-disqualified-after-a-prompt-injection.md) | A candidate tries to talk the agent into marking him qualified, then admits he has no car license. |
| [Needs review: an expired license](05-needs-review-expired-license.md) | A candidate whose license expired in August, with a renewal appointment in two weeks. |
| [Re-engagement: silent overnight, back in the morning](06-re-engagement-overnight.md) | A candidate who stops answering at 20:34 and comes back the next morning. |
