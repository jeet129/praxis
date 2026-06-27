---
name: stack-java-spring
description: Idiomatic Spring Boot implementation pack — project layout, layering (hexagonal/clean architecture inside Spring), dependency-injection hygiene, Spring Data, Bean Validation, configuration management, build (Maven/Gradle), packaging (uber-jar + container), and test idioms (JUnit 5 + AssertJ + Testcontainers).
---

# Stack — Java / Spring Boot


<!-- praxis:description:full -->
## Full description

Idiomatic Spring Boot implementation pack — project layout, layering (hexagonal/clean architecture inside Spring), dependency-injection hygiene, Spring Data, Bean Validation, configuration management, build (Maven/Gradle), packaging (uber-jar + container), and test idioms (JUnit 5 + AssertJ + Testcontainers). Complements `engineering-standards/references/java-spring.md` (which carries the standards-side rules) with the *implementation-side* idioms a developer needs to write Spring code that conforms. Use whenever a developer is implementing on Java/Spring Boot, scaffolding a new Spring service, or evaluating Spring-specific patterns.

<!-- praxis:description:end -->


<!-- praxis:metadata:begin -->
```yaml
capability: stack
domain: backend
state: active
dependencies:
 - engineering-standards
triggers:
 - "implementing a feature on Spring Boot"
 - "scaffolding a new Spring service"
 - "evaluating Spring conventions for a slice"
 - "choosing between Spring patterns (e.g., WebMVC vs WebFlux)"
 - "configuring Spring testing"
outputs:
 - scaffolded module/package conforming to the layout
 - code conforming to standards + Spring idioms
 - build config (Maven/Gradle)
 - test scaffolds (JUnit 5 + Testcontainers)
consumers:
 - backend-developer
 - code-review
 - testing-strategy
references:
 - spring-boot-3.md
 - quarkus.md
```
<!-- praxis:metadata:end -->

Implementation idioms for Spring Boot 3.x on Java 17+. Complements `engineering-standards/references/java-spring.md` — that file is the *bar*; this file is the *playbook*.

## Project layout

Bounded-context-first, mirrored from `engineering-standards`:

```
src/main/java/com/company/product/
├── billing/
│ ├── domain/
│ │ ├── Order.java aggregate
│ │ ├── OrderId.java value object
│ │ ├── OrderRepository.java port (interface)
│ │ └── events/OrderPlaced.java domain event
│ ├── application/
│ │ ├── PlaceOrderUseCase.java
│ │ └── ports/PaymentGateway.java port
│ ├── infrastructure/
│ │ ├── persistence/
│ │ │ ├── JpaOrderRepository.java adapter (impl)
│ │ │ └── OrderEntity.java JPA entity (separate from domain)
│ │ └── external/StripePaymentGateway.java
│ └── presentation/
│ ├── OrderController.java
│ ├── OrderRequest.java DTO
│ └── OrderResponse.java DTO
├── auth/
│ └── ...
└── shared/ default empty
```

Top-level packages by domain, not by layer. `controllers/` + `services/` + `repos/` at the top is a violation.

## Configuration

`application.yml` (one file; profile-specific overrides via `application-{profile}.yml`):

```yaml
spring:
 application:
 name: ${SERVICE_NAME:order-service}
 datasource:
 url: ${DB_URL}
 username: ${DB_USER}
 password: ${DB_PASSWORD}
 jpa:
 hibernate:
 ddl-auto: validate # NEVER 'update' in prod
 properties:
 hibernate.jdbc.batch_size: 25
server:
 port: ${PORT:8080}
 shutdown: graceful
 servlet:
 context-path: /api
management:
 endpoints.web.exposure.include: health,info,metrics,prometheus
 endpoint.health.probes.enabled: true # for K8s liveness/readiness
logging:
 level:
 root: INFO
 com.company.product: ${APP_LOG_LEVEL:INFO}
```

Secrets come from environment via `secrets-config` skill — never committed.

## Dependency injection

Constructor injection only. No field injection (`@Autowired` on fields is a blocker violation).

```java
@Service
public class PlaceOrderUseCase {
 private final OrderRepository orders;
 private final PaymentGateway payments;
 private final ApplicationEventPublisher events;

 public PlaceOrderUseCase(
 OrderRepository orders,
 PaymentGateway payments,
 ApplicationEventPublisher events) {
 this.orders = orders;
 this.payments = payments;
 this.events = events;
 }

 @Transactional
 public OrderId execute(PlaceOrderCommand cmd) {
 var order = Order.place(cmd);
 orders.save(order);
 payments.charge(order.id(), cmd.amount());
 events.publishEvent(new OrderPlaced(order.id()));
 return order.id();
 }
}
```

Lombok's `@RequiredArgsConstructor` is acceptable to reduce boilerplate but optional. Records for immutable DTOs and value objects (`record OrderRequest(...)`).

## REST controllers

Thin. Map HTTP → application service → HTTP. No business logic.

```java
@RestController
@RequestMapping("/orders")
@Validated
public class OrderController {
 private final PlaceOrderUseCase placeOrder;

 public OrderController(PlaceOrderUseCase placeOrder) {
 this.placeOrder = placeOrder;
 }

 @PostMapping
 @ResponseStatus(HttpStatus.CREATED)
 public OrderResponse create(@Valid @RequestBody OrderRequest req) {
 var id = placeOrder.execute(req.toCommand());
 return OrderResponse.of(id);
 }
}
```

Error translation via `@ControllerAdvice`:

```java
@RestControllerAdvice
public class ErrorHandler {
 @ExceptionHandler(DomainException.class)
 ResponseEntity<ErrorBody> domain(DomainException e) {
 return ResponseEntity.status(e.status()).body(ErrorBody.of(e));
 }
 @ExceptionHandler(MethodArgumentNotValidException.class)
 ResponseEntity<ErrorBody> validation(MethodArgumentNotValidException e) {
 // ...
 }
}
```

## Persistence — JPA boundaries

JPA entities are *adapters*, not domain objects. Map them explicitly:

```java
// infrastructure/persistence/OrderEntity.java
@Entity
@Table(name = "orders")
class OrderEntity {
 @Id private UUID id;
 private String status;
 private BigDecimal amount;
 // getters/setters or lombok @Data

 static OrderEntity from(Order order) {
 var e = new OrderEntity();
 e.id = order.id().value();
 e.status = order.status().name();
 e.amount = order.amount();
 return e;
 }

 Order toDomain() {
 return Order.reconstitute(OrderId.of(id), OrderStatus.valueOf(status), amount);
 }
}

// infrastructure/persistence/JpaOrderRepository.java
@Repository
class JpaOrderRepository implements OrderRepository {
 private final SpringDataOrderRepo data;
 JpaOrderRepository(SpringDataOrderRepo data) { this.data = data; }
 public void save(Order o) { data.save(OrderEntity.from(o)); }
 public Optional<Order> find(OrderId id) {
 return data.findById(id.value()).map(OrderEntity::toDomain);
 }
}
```

Migrations via Flyway (`db/migration/V1__create_orders.sql`). `ddl-auto: validate` in production; `update` is a blocker violation.

## Validation

- Bean Validation on DTOs at the controller boundary (`@Valid @RequestBody`).
- Domain invariants in domain-object constructors / factory methods — invalid state should be unconstructable.

```java
public record OrderRequest(
 @NotNull @Size(min = 1, max = 100) String customerId,
 @NotNull @DecimalMin("0.01") BigDecimal amount,
 @NotEmpty List<@Valid LineItem> items
) {
 public PlaceOrderCommand toCommand() { /* ... */ }
}
```

## Async and concurrency

- `@Async` only with an explicit configured `ThreadPoolTaskExecutor` — never the default `SimpleAsyncTaskExecutor` (creates a thread per call; production hazard).
- `@Transactional` only at the application-service layer; never on controllers, never on private methods (self-invocation defeats it).
- Spring's `@Retryable` for limited use; for serious resilience use Resilience4j (circuit breaker, retry, bulkhead, rate limiter).

## Testing

JUnit 5 + AssertJ + Mockito + Testcontainers. **No embedded H2** as a Postgres substitute — use a real Postgres container.

```java
@SpringBootTest
@Testcontainers
class PlaceOrderUseCaseIT {
 @Container
 static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

 @DynamicPropertySource
 static void props(DynamicPropertyRegistry r) {
 r.add("spring.datasource.url", postgres::getJdbcUrl);
 r.add("spring.datasource.username", postgres::getUsername);
 r.add("spring.datasource.password", postgres::getPassword);
 }

 @Autowired PlaceOrderUseCase useCase;

 @Test
 void placesOrder_whenTenantHasCredit_persistsAndReturnsId() {
 var id = useCase.execute(samplePlaceOrderCommand());
 assertThat(id).isNotNull();
 }
}
```

Test layering:

- **Unit tests** — pure domain logic; no Spring context. Fast.
- **Slice tests** — `@WebMvcTest`, `@DataJpaTest`, `@JsonTest` for narrow Spring concerns. Medium.
- **Integration tests** — `@SpringBootTest` + Testcontainers. Slow but real. The few critical end-to-end paths.

## Build and packaging

Maven *or* Gradle — pick one per project. Both supported.

Production Dockerfile (multi-stage, distroless, non-root):

```dockerfile
FROM eclipse-temurin:21-jdk-jammy AS build
WORKDIR /workspace
COPY pom.xml .
COPY src ./src
RUN ./mvnw -B clean package -DskipTests

FROM gcr.io/distroless/java21-debian12:nonroot
WORKDIR /app
COPY --from=build /workspace/target/*.jar app.jar
USER nonroot
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
```

Spring Boot's layered jars + buildpacks are also an option; either is acceptable.

## Observability hooks 

- Micrometer for metrics; expose at `/actuator/prometheus`.
- Structured logging via `logstash-logback-encoder`. MDC for correlation ID set in a `Filter` at the request boundary.
- Liveness/readiness probes via `/actuator/health/liveness` and `/actuator/health/readiness`.

Full observability instrumentation is owned by the `observability` skill; this stack pack provides the surface (Spring Boot Actuator endpoints + probe paths) that `observability` wires.

## Sub-variant references

For framework-specific deep-dives:

- `references/spring-boot-3.md` — Spring Boot 3.x specifics, virtual threads, native compilation considerations.
- `references/quarkus.md` — Quarkus alternative when fast cold-start matters (serverless, container-per-request).

## Mode handling (G/B)

**Greenfield.** Scaffold a fresh Spring Boot project per this layout. `spring-boot-starter-parent` or Spring's `spring-initializr` API for the skeleton; replace the default flat layout with the bounded-context-first layout above.

**Brownfield.** Read `.repo-intel/conventions.md` first. If the existing Spring project follows a different layout, match it for new code and flag the divergence in an ADR — don't refactor the existing layout on a feature PR.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Field injection is shorter." | Field injection breaks constructor immutability and complicates testing. Constructor injection is the bar. |
| "Lombok @Data on entities is convenient." | @Data generates equals/hashCode that misbehave on JPA proxies + lazy loading. Use explicit equality. |
| "Spring auto-configures everything; I don't need to think about it." | Magic that you don't understand is magic that fails in mysterious ways. Read the actual auto-config; know what's wired. |
| "Annotations are fine everywhere; let Spring sort it out." | @Transactional placement matters (interface vs class, public vs private). Mis-placed annotations silently don't activate. |
| "Reactor / WebFlux because reactive scales better." | Reactive scales differently, not better. Add complexity only when measured load justifies it. |
| "Native-image (GraalVM) is the future; start there." | Native imposes reflection limits + build-time work. Use only when startup time / memory savings justify the cost. |

## Verification

You are done when:

- [ ] Constructor injection used throughout (no `@Autowired` fields).
- [ ] Spring Boot config externalized via `application.yml` + `@ConfigurationProperties` (not scattered `@Value`).
- [ ] Transaction boundaries documented (where `@Transactional` lives; which propagation).
- [ ] DTOs distinct from entities; mapping layer explicit.
- [ ] Testcontainers used for integration tests (no H2 substitutes for production stores).
- [ ] Actuator endpoints exposed appropriately; secured for production.
- [ ] Logging via SLF4J with structured fields; no `System.out`.
- [ ] Brownfield: existing conventions matched; divergence captured in ADR.

Evidence to check:
- Slice tests (`@WebMvcTest`, `@DataJpaTest`) pass; bean-graph errors caught early.
- Integration tests against Testcontainers exercise the real DB.

## Anti-patterns

- `@Autowired` on fields (use constructor injection).
- Domain logic in controllers or repository classes.
- JPA entities reused as domain objects (couples persistence to domain).
- `Optional.get()` without `isPresent()` check.
- `spring.jpa.hibernate.ddl-auto: update` in production.
- Default `SimpleAsyncTaskExecutor` (creates threads unboundedly).
- Catch-all exception handlers that swallow errors.
- Static utility classes that should be Spring components.
