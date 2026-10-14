# 08_faq_midflow_barcelona: Candidate asks about pay mid-flow, then asks something the FAQ doesn't cover

**PASS** · expected `qualified`, got `qualified` · 10 candidate messages · 6.3 min · $0.0542

*Thursday 22 October 2026*

**Alex** · 17:45  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 17:45  
> vale, empezamos. ¿cuánto pagan?

**Alex** · 17:45  
El pago depende de la ciudad y de las horas, y el reclutador te dará la cifra exacta en la entrevista. ¿Me dices tu nombre y apellidos para empezar?

> **Candidate** · 17:46  
> Marc Puig Serra

**Alex** · 17:46  
Genial, anotado. ¿Tienes el carnet de conducir en vigor?

> **Candidate** · 17:47  
> vale, y es con moto o bici el reparto?

**Alex** · 17:47  
Sobre el vehículo, lo confirmará el reclutador; lo que sí necesitas es el carnet de conducir en vigor. ¿Lo tienes?

> **Candidate** · 17:47  
> sí, carnet B

**Alex** · 17:47  
Perfecto, anotado. ¿En qué ciudad vives y en qué barrio?

> **Candidate** · 17:47  
> Barcelona, en Gràcia. Tengo 1 año en Uber Eats y 2 en Glovo

**Alex** · 17:47  
Genial, anotado. ¿Buscas jornada completa, media jornada, fines de semana o una combinación?

> **Candidate** · 17:48  
> jornada completa. y cuánto se cobra? es por hora o por pedido?

**Alex** · 17:48  
Jornada completa, anotado. El pago depende de la ciudad y las horas, y el reclutador te dará la cifra exacta en la entrevista, ¿qué turnos te vienen mejor: mañanas, tardes, noches o flexible?

> **Candidate** · 17:48  
> noches, desde las 8 de la noche más o menos. tardes no

**Alex** · 17:48  
Vale, noches anotado. ¿Cuándo podrías empezar?

> **Candidate** · 17:49  
> antes de eso, dais seguro médico privado?

**Alex** · 17:49  
Eso lo confirmará el reclutador, yo no tengo ese dato. ¿Cuándo podrías empezar?

> **Candidate** · 17:50  
> mañana mismo si hace falta

**Alex** · 17:50  
¡Gracias, Marc! Repasemos: Marc Puig Serra, carnet de conducir: sí, Barcelona, jornada completa, noches, Uber Eats 1 año, Glovo 2 años, empiezas el viernes 23 de octubre. ¿Está todo bien?

> **Candidate** · 17:51  
> sí, todo bien. cuándo me llama el reclutador?

**Alex** · 17:51 *(close)*  
¡Listo, Marc! Un reclutador de Grupo Sazón te escribirá en los próximos días para concertar una entrevista. ¡Gracias por tu tiempo!

## Final record

```json
{
  "conversation_id": "eval-08_faq_midflow_barcelona",
  "status": "qualified",
  "language": "es",
  "full_name": "Marc Puig Serra",
  "has_driver_license": true,
  "country": "ES",
  "city": "barcelona",
  "availability": [
    "full_time"
  ],
  "preferred_schedule": [
    "evening"
  ],
  "delivery_experience": [
    {
      "platform": "uber_eats",
      "years": 1.0
    },
    {
      "platform": "glovo",
      "years": 2.0
    }
  ],
  "start_date": "2026-10-23",
  "flags": [],
  "disqualify_reason": null,
  "review_reasons": [],
  "summary": "Marc Puig Serra queda como cualificado, sin motivos de revisión ni banderas. Tiene carnet de conducir, vive en Barcelona (Gràcia), busca jornada completa en turno de noche (desde las 20:00 aproximadamente, y no quiere tardes) y tiene 1 año de experiencia en Uber Eats y 2 en Glovo. Dice que puede empezar de inmediato (\"mañana mismo si hace falta\"), y el registro fija el inicio el 23 de octubre de 2026. Antes de llamar, conviene saber que preguntó por el pago (si es por hora o por pedido) y por si hay seguro médico privado, y Alex no pudo darle ninguna respuesta concreta; también preguntó cuándo lo llamaría el reclutador, y solo se le dijo que sería en los próximos días."
}
```
