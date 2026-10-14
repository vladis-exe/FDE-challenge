# English: a British candidate in Valencia

*Spain · outcome `qualified` · 9 candidate messages · eval scenario `03_en_happy_valencia`*

An English-speaking candidate, screened entirely in English. Tom answers the city question with only his neighborhood, in its Spanish spelling ("ruzafa"), and his experience is on Deliveroo, a platform that isn't on the list.

**What to notice**

- Alex switches to English from the candidate's first reply and stays there.
- "ruzafa" alone resolves to Valencia: neighborhoods are aliases in the service-area config.
- Deliveroo is stored as `other` with the 3 years kept (the platform list is closed so recruiters can filter on it), and the recruiter summary says it was Deliveroo.

## Conversation

*Thursday 22 October 2026*

**Alex** · 10:15  
Hi! I'm Alex, Grupo Sazón's virtual assistant (AI) 👋 It's 7 quick questions about the delivery driver job, about 3 minutes. Your details are only used for this application: https://gruposazon.example/privacidad. Shall we start?

> **Candidate** · 10:16  
> yeah sure go ahead

**Alex** · 10:16  
Great, let's go! Could you tell me your full name, first name and surname?

> **Candidate** · 10:17  
> Tom Whitaker

**Alex** · 10:17  
Noted, Tom, thanks! Do you have a valid driving license?

> **Candidate** · 10:17  
> yeah got a spanish one now

**Alex** · 10:17  
Thanks for that, Tom! Which city are you based in, and what's your neighborhood?

> **Candidate** · 10:18  
> ruzafa

**Alex** · 10:18  
Got it, Ruzafa in Valencia, noted! Are you looking for full-time, part-time, weekends, or a mix of those?

> **Candidate** · 10:19  
> part time and weekends

**Alex** · 10:19  
Got it, part-time and weekends noted. Which shifts suit you best: mornings, afternoons, evenings, or flexible?

> **Candidate** · 10:19  
> afternoons and evenins

**Alex** · 10:19  
Got it, afternoons and evenings noted. Have you done delivery work before, like Glovo, Uber Eats or Just Eat, and for how long?

> **Candidate** · 10:20  
> yeah 3 years on deliveroo in bristol before i moved here

**Alex** · 10:20  
Got it, Tom, 3 years on Deliveroo in Bristol noted! When could you start?

> **Candidate** · 10:21  
> monday 2 november

**Alex** · 10:21  
Thanks, Tom! Quick check: Tom Whitaker, driver's license: yes, Valencia, part-time and weekends, afternoons and evenings, another platform 3 years, starting Monday 2 November. Is everything right?

> **Candidate** · 10:21  
> yeah all good

**Alex** · 10:21 *(close)*  
All done, Tom! A Grupo Sazón recruiter will message you in the next few days to set up an interview. Thanks for your time!

## What the recruiter gets

> Tom Whitaker queda como calificado para la vacante de conductor, sin banderas ni motivos de revisión. Vive en Valencia (barrio de Ruzafa) y busca trabajo a tiempo parcial y fines de semana, en turnos de tarde y noche; puede empezar el 2 de noviembre de 2026. Tiene carnet de conducir y 3 años de experiencia en Deliveroo (Bristol), registrada como otra plataforma. No hubo preguntas sin respuesta ni incidencias en la conversación, y el candidato confirmó que sus datos eran correctos.

```json
{
  "conversation_id": "eval-03_en_happy_valencia",
  "vacancy_id": "driver",
  "status": "qualified",
  "language": "en",
  "fields": {
    "full_name": "Tom Whitaker",
    "has_driver_license": true,
    "location": {
      "country": "ES",
      "city": "valencia"
    },
    "availability": [
      "part_time",
      "weekends"
    ],
    "schedule": [
      "afternoon",
      "evening"
    ],
    "experience": [
      {
        "platform": "other",
        "years": 3.0
      }
    ],
    "start_date": "2026-11-02"
  },
  "flags": [],
  "disqualify_reason": null,
  "review_reasons": [],
  "preference_score": 0
}
```
