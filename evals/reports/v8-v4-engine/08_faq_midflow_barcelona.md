# 08_faq_midflow_barcelona: Candidate asks about pay mid-flow, then asks something the FAQ doesn't cover

**PASS** · expected `qualified`, got `qualified` · 13 candidate messages · 8.6 min · $0.0098

*Thursday 22 October 2026*

**Alex** · 17:45  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 17:45  
> Vale, empezamos

**Alex** · 17:45  
Genial, pues empecemos. ¿Me dices tu nombre y apellido completos?

> **Candidate** · 17:46  
> Marc Puig Serra

**Alex** · 17:46  
Gracias, Marc, lo tengo anotado. ¿Tienes carnet de conducir en vigor, sí o no?

> **Candidate** · 17:47  
> Vale, y el sueldo cuánto sería más o menos?

**Alex** · 17:47  
El sueldo depende de la ciudad y de las horas, y el reclutador te dará la cifra exacta en la entrevista. Mientras tanto, ¿tienes carnet de conducir en vigor, sí o no?

> **Candidate** · 17:47  
> Vale, y el carnet de conducir sí, es el B.

**Alex** · 17:47  
Perfecto, anotado. ¿En qué ciudad vives y en qué barrio?

> **Candidate** · 17:47  
> Barcelona, Gràcia. Y oye, ¿el sueldo en Barcelona más o menos cuánto sale por hora?

**Alex** · 17:47  
El pago depende de la ciudad y las horas, y el reclutador te lo confirmará en la entrevista. ¿Buscas jornada completa, media jornada, fines de semana o una combinación?

> **Candidate** · 17:48  
> jornada completa. y cuánto se cobra? es por hora o por pedido?

**Alex** · 17:48  
El pago depende de la ciudad y las horas, y el reclutador te dará la cifra exacta. ¿Qué turnos te van bien: mañanas, tardes, noches o flexible?

> **Candidate** · 17:48  
> Noches, de 8 pm en adelante. Por la tarde no puedo.

**Alex** · 17:48  
Anotado, turno de noches desde las 20:00. ¿Has trabajado antes en reparto con Glovo, Uber Eats, Just Eat u otra app, y cuánto tiempo?

> **Candidate** · 17:49  
> antes de eso, dais seguro médico privado?

**Alex** · 17:49  
Eso no lo tengo confirmado, el reclutador te dirá lo del seguro médico. ¿Has trabajado antes en reparto con Glovo, Uber Eats, Just Eat, Rappi o DiDi Food, y cuánto tiempo?

> **Candidate** · 17:50  
> Sí, 1 año en Uber Eats y 2 años en Glovo

**Alex** · 17:50  
Anotado, 1 año en Uber Eats y 2 en Glovo. ¿Para cuándo podrías empezar?

> **Candidate** · 17:51  
> mañana mismo si hace falta

**Alex** · 17:51  
¡Gracias, Marc! Repasemos: Marc Puig Serra, carnet de conducir: sí, Barcelona, jornada completa, noches, Uber Eats 1 año, Glovo 2 años, empiezas el jueves 22 de octubre. ¿Está todo bien?

> **Candidate** · 17:51  
> Casi todo bien. Lo de empezar mañana, no el jueves 22. Hoy es jueves 22 así que mañana es viernes 23. Y lo del carnet es el B, por si lo quieres apuntar así.

**Alex** · 17:51  
¡Gracias, Marc! Repasemos: Marc Puig Serra, carnet de conducir: sí, Barcelona, jornada completa, noches, Uber Eats 1 año, Glovo 2 años, empiezas el viernes 23 de octubre. ¿Está todo bien?

> **Candidate** · 17:52  
> Casi. Lo del carnet es el B, no solo sí. Y lo de Barcelona, Gràcia, mejor. Lo demás bien.

**Alex** · 17:52  
Entendido, Marc. ¿Qué dato del resumen quieres que corrija: el carnet, la ciudad o el turno?

> **Candidate** · 17:53  
> Ninguno más, ya está. Carnet B, Barcelona Gràcia, lo demás bien.

**Alex** · 17:53 *(close)*  
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
    "availability": [
      "full_time"
    ],
    "schedule": [
      "evening"
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
  "summary": "Marc Puig Serra cumple los requisitos para el puesto de repartidor (status: qualified, sin motivos de revisión ni banderas). Está disponible a jornada completa en turno de noche, vive en Barcelona (comentó que en Gràcia), tiene carnet de conducir tipo B y cuenta con 1 año de experiencia en Uber Eats y 2 en Glovo; puede empezar el viernes 23 de octubre de 2026. Durante el resumen corrigió la fecha de inicio (Alex había anotado el jueves 22) y precisó el tipo de carnet y la zona, aunque el registro solo guarda \"Barcelona\" como ciudad. Además, preguntó si ofrecen seguro médico privado y Alex no pudo confirmarlo, así que conviene que el reclutador se lo aclare.",
  "preference_score": 0
}
```
