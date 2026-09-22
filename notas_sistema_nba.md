# Sistema multimodal

## Servidor
- **Web Portfolio**
- **Análisis NBA** → Uso de datos, estadísticas y $ para determinar qué jugador de la liga se adapta mejor a cada equipo.

De esta forma se podrá detectar el **mejor fit para tu equipo**.

**¿A qué precio?** → Mejor fit teniendo en cuenta traspasos. Va a ser capaz de determinar qué jugadores estarán valorados y cuáles formarán la mejor plantilla posible.

## Posibles problemas
- **Jugadores jóvenes** → Pocos datos.
- **Jugadores peores** → $ bajos.
- **Traspasos imposibles** → Quizá el jugador X es el mejor fit para la plantilla.

## Ideas
- ¿Dividir los jugadores por aprendizaje no supervisado (PCA)?
- Todas las semanas recoger nuevas estadísticas + recalcular.
- Sistema capaz de, juntando varios jugadores, determinar el mejor acompañante.

## ¿Qué pregunta estoy respondiendo?
- ¿Qué jugador encajaría mejor en mi plantilla?
  - ¿Qué gano?
  - ¿Cuánto debería costar comparado con jugadores similares?

## Notas técnicas
- Habrá que normalizar; además, hay estadísticas que son negativas, como: partidos perdidos por lesiones.
