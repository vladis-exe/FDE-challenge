# 06_correction_at_confirm_guadalajara: Candidate corrects two fields in one message at the read-back

**PASS** · expected `qualified`, got `qualified` · 10 candidate messages · 6.8 min · $0.0078

*Tuesday 20 October 2026*

**Alex** · 12:00  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 12:00  
> jaja hola, sí va

**Alex** · 12:00  
¡Genial! Para empezar, ¿me dices tu nombre y apellido?

> **Candidate** · 12:01  
> María Guadalupe Torres Ríos

**Alex** · 12:01  
Gracias, María Guadalupe, anotado. ¿Tienes licencia de manejo vigente, sí o no?

> **Candidate** · 12:02  
> sí tengo licencia de manejo, vigente jaja

**Alex** · 12:02  
¡Buenísimo! ¿En qué ciudad vives y en qué colonia?

> **Candidate** · 12:02  
> vivo en guadalajara, colonia providencia

**Alex** · 12:02  
Perfecto, anotado Guadalajara. ¿Qué horario te funciona mejor: tiempo completo, medio tiempo, fines de semana o una combinación?

> **Candidate** · 12:03  
> medio tiempo oki

**Alex** · 12:03  
¡Genial, medio tiempo anotado! ¿Qué turno te funciona mejor: mañanas, tardes, noches u horario flexible?

> **Candidate** · 12:04  
> mañanas oki

**Alex** · 12:04  
¡Mañanas anotado! ¿Has trabajado antes en reparto, con Uber Eats, Rappi, DiDi Food u otra app, y cuánto tiempo?

> **Candidate** · 12:05  
> no nunca he repartido

**Alex** · 12:05  
Gracias por contarme, María, no pasa nada. ¿Desde cuándo podrías empezar a trabajar?

> **Candidate** · 12:05  
> jaja pues el 2 de noviembre

**Alex** · 12:05  
¡Gracias, María! Repasemos: María Guadalupe Torres Ríos, licencia de manejo: sí, Guadalajara, medio tiempo, mañanas, sin experiencia en reparto, empiezas el lunes 2 de noviembre. ¿Está todo bien?

> **Candidate** · 12:06  
> ah espérate jaja ya no, mejor tiempo completo porque ya me salgo de la tienda, y entonces puedo empezar desde el lunes 26

**Alex** · 12:06  
¡Gracias, María! Repasemos: María Guadalupe Torres Ríos, licencia de manejo: sí, Guadalajara, tiempo completo, mañanas, sin experiencia en reparto, empiezas el lunes 26 de octubre. ¿Está todo bien?

> **Candidate** · 12:06  
> sí, todo bien jaja. solo que lo de colonia providencia también va

**Alex** · 12:06 *(close)*  
¡Listo, María! Un reclutador de Grupo Sazón te escribirá en los próximos días para concertar una entrevista. ¡Gracias por tu tiempo!

## Final record

```json
{
  "conversation_id": "eval-06_correction_at_confirm_guadalajara",
  "vacancy_id": "driver",
  "status": "qualified",
  "language": "es",
  "fields": {
    "full_name": "María Guadalupe Torres Ríos",
    "has_driver_license": true,
    "location": {
      "country": "MX",
      "city": "guadalajara"
    },
    "availability": [
      "full_time"
    ],
    "schedule": [
      "morning"
    ],
    "experience": [],
    "start_date": "2026-10-26"
  },
  "flags": [],
  "disqualify_reason": null,
  "review_reasons": [],
  "summary": "María Guadalupe Torres Ríos cumple los requisitos para el puesto de Repartidor (estado: calificada, sin motivos de revisión ni banderas). Está en Guadalajara, tiene licencia de manejo, disponibilidad de tiempo completo en turno de mañana, sin experiencia previa en reparto, y puede empezar el 26 de octubre de 2026. Durante la confirmación corrigió sus datos: primero dijo medio tiempo con inicio el 2 de noviembre, y luego cambió a tiempo completo con inicio el lunes 26 porque dejará su empleo actual, así que conviene reconfirmar disponibilidad y fecha al llamar. Al final añadió que \"lo de colonia Providencia también va\", un comentario que Alex no aclaró ni quedó registrado en ningún campo, por lo que vale la pena preguntarle a qué se refiere.",
  "preference_score": 0.0
}
```
