# 08_faq_midflow_barcelona: Candidate asks about pay mid-flow, then asks something the FAQ doesn't cover

**PASS** · expected `qualified`, got `qualified` · 10 candidate messages · 6.9 min · $0.0085

*Thursday 22 October 2026*

**Alex** · 17:45  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 17:45  
> Vale, empezamos

**Alex** · 17:45  
Genial, empecemos. ¿Me dices tu nombre y apellido?

> **Candidate** · 17:46  
> Marc Puig Serra

**Alex** · 17:46  
¡Gracias, Marc! ¿Tienes carnet de conducir en vigor?

> **Candidate** · 17:47  
> Vale, y el carnet qué tal? Pero antes una cosa: ¿el sueldo es fijo o por reparto?

**Alex** · 17:47  
El pago depende de la ciudad y de las horas; el reclutador te dará la cifra exacta en la entrevista. Y para seguir, ¿tienes el carnet de conducir en vigor, sí o no?

> **Candidate** · 17:47  
> Sí, carnet B. Vale, lo del sueldo lo miro con el reclutador entonces. ¿Y en qué zona de Barcelona trabajaría?

**Alex** · 17:47  
¡Genial, anotado el carnet B! Lo de la zona exacta de Barcelona te lo confirmará el reclutador; ahora, ¿en qué ciudad vives?

> **Candidate** · 17:47  
> Barcelona, en Gràcia. Y oye, ¿y la disponibilidad? Yo solo puedo de noche, desde las 8 más o menos.

**Alex** · 17:47  
Perfecto, Barcelona y de noche anotado. La disponibilidad exacta de horario te la confirmará el reclutador; ahora, ¿buscas jornada completa, media jornada, fines de semana o una combinación?

> **Candidate** · 17:48  
> jornada completa. y cuánto se cobra? es por hora o por pedido?

**Alex** · 17:48  
Anotado, jornada completa. ¿Tienes experiencia previa en reparto, con Glovo, Uber Eats o similar, y cuánto tiempo?

> **Candidate** · 17:48  
> antes de eso, dais seguro médico privado?

**Alex** · 17:48  
Eso del seguro médico te lo confirmará el reclutador. ¿Has trabajado antes en reparto, con Glovo, Uber Eats o similar, y cuánto tiempo?

> **Candidate** · 17:50  
> Sí, 1 año en Uber Eats y 2 años en Glovo. ¿Y cuándo empezaría? Yo podría mañana.

**Alex** · 17:50  
¡Genial, anotado: 1 año en Uber Eats y 2 en Glovo! Cuando terminemos, un reclutador revisa tus respuestas y te escribe para concertar una entrevista.

**Alex** · 17:50  
¡Gracias, Marc! Repasemos: Marc Puig Serra, carnet de conducir: sí, Barcelona, jornada completa, noches, Uber Eats 1 año, Glovo 2 años, empiezas el viernes 23 de octubre. ¿Está todo bien?

> **Candidate** · 17:50  
> mañana mismo si hace falta

**Alex** · 17:50  
Vale, Marc, lo de empezar mañana lo verá el reclutador. ¿Qué dato del resumen quieres que cambiemos?

> **Candidate** · 17:51  
> Nada, todo bien. Lo de empezar mañana es lo que te dije, ¿no? Ya está.

**Alex** · 17:51 *(close)*  
¡Listo, Marc! Un reclutador de Grupo Sazón te escribirá en los próximos días para concertar una entrevista. ¡Gracias por tu tiempo!

## Final record

```json
{
  "conversation_id": "eval-08_faq_midflow_barcelona",
  "vacancy_id": "driver",
  "status": "qualified",
  "language": "es",
  "fields": {
    "full_name": "Marc Puig Serra",
    "has_driver_license": true,
    "location": {
      "country": "ES",
      "city": "barcelona"
    },
    "schedule": [
      "evening"
    ],
    "availability": [
      "full_time"
    ],
    "experience": [
      {
        "platform": "uber_eats",
        "years": 1.0
      },
      {
        "platform": "glovo",
        "years": 2.0
      }
    ],
    "start_date": "2026-10-23"
  },
  "flags": [],
  "disqualify_reason": null,
  "review_reasons": [],
  "summary": "Marc Puig Serra queda como cualificado para el puesto de Repartidor, sin motivos de descarte ni de revisión. Vive en Barcelona, busca jornada completa en horario de noche, tiene carnet de conducir y acumula 3 años de experiencia en reparto (1 año en Uber Eats y 2 en Glovo). La fecha de inicio registrada es el 23 de octubre de 2026, pero el candidato dijo que podría empezar \"mañana\" y lo repitió después, así que conviene confirmar con él la fecha real. Además, hizo dos preguntas que Alex no pudo responder y que deberá resolver el reclutador: cuánto se cobra (si es por hora o por pedido) y si hay seguro médico privado.",
  "preference_score": 0.0
}
```
