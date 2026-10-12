"""Policy: the screening state machine. Pure code, no LLM calls.

`decide(state, extraction, message)` takes the conversation state and what the
LLM read in the candidate's message (an Extraction), and returns the new state,
the events, and what to reply: a fixed message, or a ReplyPlan for the LLM to
phrase. Every eligibility decision, stage change and outcome is made here, from
validated values only, so nothing a candidate writes to the model can change an
outcome (DECISIONS D3).

Stages follow the spec order:
    CONSENT → NAME → LICENSE → LOCATION → AVAILABILITY → SCHEDULE → EXPERIENCE
    → START_DATE → CONFIRM → DONE
The stage is always "the first field still missing"; any message may fill any
field, so a candidate who answers several questions at once skips ahead.

Transition table. Rules are checked top to bottom; the first match wins.

| #  | When                                         | Then                                                     | Reply                         |
|----|----------------------------------------------|----------------------------------------------------------|-------------------------------|
|    | **Before reading the message**               |                                                          |                               |
| 1  | status = opted_out                           | nothing changes                                          | none                          |
| 2  | media, no text                               | event media_received; no attempt is used                 | fixed: media                  |
| 3  | status = abandoned                           | status → in_progress (a late reply resumes), go on        | (from the rules below)        |
| 4  | status = qualified / needs_review / disqualified | nothing changes                                      | FAQ answer if asked, else fixed: after_close |
|    | **Any stage, in_progress**                   |                                                          |                               |
| 5  | intent = opt_out                             | status → opted_out                                       | close: opt_out                |
| 6  | intent = human_request                       | status → needs_review, reason human_requested            | close: human_requested        |
| 7  | intent = offtopic or abuse, strikes < max    | strikes += 1, event offtopic; extracted values ignored    | redirect + re-ask current     |
| 8  | intent = offtopic or abuse, strikes = max    | status → needs_review, reason offtopic or abuse          | close: flagged                |
|    | **CONSENT**                                  |                                                          |                               |
| 9  | consent = no                                 | status → opted_out, profile left empty                   | close: consent_declined       |
| 10 | consent = yes, or any field given            | consent_at = now, event consent_given; apply fields (16) | next ask                      |
| 11 | anything else (question, small talk)         | nothing changes                                          | FAQ answer if asked + ask consent |
|    | **Out-of-area confirmation pending**         |                                                          |                               |
| 12 | city given that is served                    | pending cleared, location accepted                       | next ask                      |
| 13 | the same unserved city again, or confirm     | status → disqualified (out_of_area)                      | close: out_of_area (waitlist) |
| 14 | another unserved city                        | pending = that city                                      | ask out_of_area               |
| 15 | deny, no city                                | pending cleared, location attempt used                   | ask location                  |
|    | (otherwise: FAQ answer if asked, ask out_of_area again)  |                                              |                               |
|    | **Collecting fields (NAME … START_DATE, and CONFIRM corrections)** |                                    |                               |
| 16 | each field given, validated in spec order:   |                                                          |                               |
|    |   accept                                     | value stored with source message; event field_accepted (field_corrected if it changed) | acknowledged |
|    |   license = no                               | status → disqualified (no_license); stop                 | close: no_license             |
|    |   flag (unclear license)                     | field flagged + note, reason license_unclear; move on    | acknowledged                  |
|    |   city not served                            | pending_confirmation = that city                         | ask out_of_area               |
|    |   city ambiguous                             | attempt used                                             | ask city_choice with options  |
|    |   reask, and it is the field being asked     | attempt used; if attempts were already at max: field flagged, reason unresolved:<field> | re-ask with reason |
|    |   reask, another field                       | ignored (it will be asked in turn)                       |                               |
| 17 | intent = answer but no field given           | attempt used on the field being asked (same max as 16)   | re-ask                        |
| 18 | after applying: a field still missing        | stage → that field                                       | FAQ answer if asked + ask it  |
| 19 | after applying: nothing missing              | stage → CONFIRM                                          | fixed: read-back              |
|    | **CONFIRM** (read-back sent)                 |                                                          |                               |
| 20 | fields given (a correction)                  | apply as in 16, then 18 or 19 (read-back again)          |                               |
| 21 | confirm                                      | status → needs_review if any field is flagged or a reason exists, else qualified | close: completed |
| 22 | deny, no field given                         | nothing changes                                          | ask which detail to change    |
| 23 | anything else                                | nothing changes                                          | FAQ answer if asked + ask confirm |

Details:
- An "attempt" is one re-ask. A field gets at most `max_attempts_per_field` (2)
  re-asks; the next failure flags it and the conversation moves on. Questions and
  small talk never use an attempt, so the agent can't loop and can't punish
  someone for asking about the job.
- A first name alone is kept, and the surname is asked once; a one-word reply
  then completes it ("Laura" + "Pérez").
- FAQ answers come only from faq.yaml (by the faq_id the LLM picked); an
  uncovered question gets "a recruiter will confirm".
- Any outcome other than in_progress also sets stage = DONE. Closes are sent as
  kind "close", so the worker never drops them.
"""
