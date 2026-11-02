Integrantes:
Domingo Ruiz-Tagle
Natalie Delgado 
Nicolas Ortiz

COMO LEVANTARLO
  docker compose up --build
  python demo.py
  Swagger:   http://localhost:8004/docs
  RabbitMQ:  http://localhost:15672  (guest / guest)
  Tests:     docker compose exec gamification python -m unittest discover -s tests

SERVICIOS
  users / channels / messages   8001-8003   Chat base
  gamification                  8004        API REST (solo lectura)
  gamification-consumer         -           Consume eventos y otorga XP
  rabbitmq                      5672        Message broker

API REST (/api/v1)
  GET /gamification/{user_id}             XP, nivel y logros
  GET /gamification/{user_id}/xp-history  Historial de XP
  GET /leaderboard                        Ranking por XP
  GET /achievements                       Catalogo de logros
  GET /events                             Eventos publicados

  GET /health  (liveness)    GET /ready  (readiness: verifica MongoDB)

DESPLIEGUE EN KUBERNETES (cluster del curso, namespace grupo-gamificacion)
  URL publica: http://gamificacion.134.199.176.3.nip.io/docs
  k8s/api.yaml      API: Deployment + Service + Ingress + HPA (2-4 replicas, CPU 60%)
  k8s/poller.yaml   Lee GET /api/v1/events de messages (servicios-base) y otorga XP
  k8s/mongodb.yaml  MongoDB propia con volumen de 1Gi
  El core del cluster no publica en un broker, por eso en el cluster se usa el
  poller en vez del consumidor de RabbitMQ. No se modifica ni redespliega el core.

  CI (.github/workflows/deploy.yml): en cada push a main construye la imagen,
  corre los tests, la publica en ghcr.io y aplica k8s/ con kubectl.
  Requiere el secret KUBECONFIG en el repo de GitHub.

  Manual:  kubectl apply -f k8s/

EVIDENCIA
  Flujo integrado contra el chat base desplegado:
    kubectl create configmap demo-flujo --from-file=demo.py
    kubectl apply -f k8s/evidencia/flujo-integrado.yaml
    kubectl logs -f job/flujo-integrado
  Escalamiento (en otra terminal: kubectl get hpa gamification-api -w):
    kubectl apply -f k8s/evidencia/carga.yaml

CAMBIOS AL CHAT BASE (solo en docker compose local)
  - Se agrego RABBITMQ_URL a messages en docker-compose.yaml.
  - Fix: insert_one(doc) agregaba un _id ObjectId al dict devuelto y causaba
    error 500; ahora se inserta una copia.

El código se realizo con ayuda de Claude Opus 5.5 basándose en la repo del profe y lo presentado en clases para la tarea pasada.
