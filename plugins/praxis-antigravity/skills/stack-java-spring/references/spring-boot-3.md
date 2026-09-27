# Reference — Spring Boot 3 (Java)

Loaded by `stack-java-spring` when Spring Boot is the chosen framework (the default for Java backend).

## When to use

Spring Boot 3 (on Java 17+) is the recommended default for Java APIs:
- The dominant Java framework with the deepest ecosystem.
- Auto-configuration handles 90% of common wiring.
- Spring Security, Data, Web, WebFlux, Cloud all integrate.
- Native-image support via GraalVM (newer; trade-offs).

Skip when:
- You want minimal startup time + low memory → Quarkus (`quarkus.md`).
- The project is a pure stream processor → use Kafka Streams / Flink directly.

## Project structure (per `stack-java-spring` SKILL — hexagonal)

```
src/main/java/com/company/product/
├── billing/
│   ├── domain/                aggregate, value objects, repository ports
│   ├── application/           use cases + ports (PaymentGateway, etc.)
│   ├── infrastructure/        adapters (JpaOrderRepository, StripeGateway)
│   └── presentation/          REST controllers + DTOs
└── shared/                    cross-cutting; default empty
```

Top-level packages by domain, not by layer.

## Build — Gradle (preferred for new) or Maven

Gradle Kotlin DSL is the recommended choice for new projects:

```kotlin
// build.gradle.kts
plugins {
    java
    id("org.springframework.boot") version "3.4.0"
    id("io.spring.dependency-management") version "1.1.6"
}

group = "com.company"
version = "1.0.0-SNAPSHOT"
java.toolchain.languageVersion = JavaLanguageVersion.of(21)

repositories { mavenCentral() }

dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.boot:spring-boot-starter-data-jpa")
    implementation("org.springframework.boot:spring-boot-starter-validation")
    implementation("org.springframework.boot:spring-boot-starter-actuator")
    runtimeOnly("org.postgresql:postgresql")
    runtimeOnly("io.micrometer:micrometer-registry-prometheus")
    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("org.testcontainers:postgresql")
    testImplementation("org.testcontainers:junit-jupiter")
}

tasks.test {
    useJUnitPlatform()
}
```

Maven equivalent in `pom.xml` with the Spring Boot parent BOM.

## Configuration

`application.yml` (Spring Boot prefers YAML):

```yaml
spring:
  application:
    name: ${SERVICE_NAME:order-service}
  datasource:
    url: ${DB_URL}
    username: ${DB_USER}
    password: ${DB_PASSWORD}
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      connection-timeout: 5000
  jpa:
    hibernate:
      ddl-auto: validate           # NEVER 'update' in prod
    properties:
      hibernate.jdbc.batch_size: 25
  flyway:
    enabled: true
    locations: classpath:db/migration

server:
  port: ${PORT:8080}
  shutdown: graceful
  servlet.context-path: /api
  tomcat.connection-timeout: 5s

management:
  endpoints.web.exposure.include: health,info,metrics,prometheus,liveness,readiness
  endpoint.health.probes.enabled: true
  health.probes.enabled: true
  metrics.tags:
    application: ${spring.application.name}

logging:
  level:
    root: INFO
    com.company.product: ${APP_LOG_LEVEL:INFO}
  pattern:
    console: '{"timestamp":"%d{yyyy-MM-dd HH:mm:ss}","level":"%level","logger":"%logger","message":"%msg","traceId":"%X{traceId}","spanId":"%X{spanId}"}%n'
```

Profile-specific overrides in `application-{profile}.yml`; profile selected via `SPRING_PROFILES_ACTIVE`.

## Constructor injection (the rule)

`@Autowired` on fields is a blocker per `stack-java-spring` SKILL. Constructor injection only:

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
    // ...
}
```

Lombok's `@RequiredArgsConstructor` is acceptable shorthand.

## REST controllers — thin

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

DTOs as records (Java 17+):

```java
public record OrderRequest(
    @NotNull @Size(min = 1) String customerId,
    @NotEmpty List<@Valid LineItem> items
) {
    public PlaceOrderCommand toCommand() { /* ... */ }
}

public record LineItem(
    @NotBlank String sku,
    @Positive int quantity
) {}
```

Error translation:

```java
@RestControllerAdvice
public class ErrorHandler {
    @ExceptionHandler(DomainException.class)
    ResponseEntity<ErrorBody> domain(DomainException e) {
        return ResponseEntity.status(e.status()).body(ErrorBody.of(e));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    ResponseEntity<ErrorBody> validation(MethodArgumentNotValidException e) {
        return ResponseEntity.badRequest()
            .body(ErrorBody.validation(e.getBindingResult().getAllErrors()));
    }
}
```

## JPA — entities are adapters, not domain

```java
// infrastructure/persistence/OrderEntity.java
@Entity
@Table(name = "orders")
class OrderEntity {
    @Id private UUID id;
    private String status;
    private BigDecimal amount;

    static OrderEntity from(Order order) { /* ... */ }
    Order toDomain() { /* ... */ }
}

@Repository
class JpaOrderRepository implements OrderRepository {
    private final SpringDataOrderRepo data;
    public JpaOrderRepository(SpringDataOrderRepo data) { this.data = data; }

    @Override public void save(Order o) { data.save(OrderEntity.from(o)); }
    @Override public Optional<Order> find(OrderId id) {
        return data.findById(id.value()).map(OrderEntity::toDomain);
    }
}

interface SpringDataOrderRepo extends JpaRepository<OrderEntity, UUID> {}
```

Migrations via Flyway (`db/migration/V1__create_orders.sql`).

## Transactions

`@Transactional` on the application service layer ONLY. NEVER on controllers (premature commit), NEVER on private methods (self-invocation defeats it).

```java
@Service
public class PlaceOrderUseCase {
    @Transactional
    public OrderId execute(PlaceOrderCommand cmd) {
        var order = Order.place(cmd);
        orders.save(order);                  // inside TX
        payments.charge(order.id(), cmd.amount());   // outside TX would be better; consider outbox
        events.publishEvent(new OrderPlaced(order.id()));
        return order.id();
    }
}
```

For at-most-once external calls in a TX, the outbox pattern (per `distributed-systems-patterns`) decouples DB commit from external publish.

## Observability — Micrometer + OTel

Spring Boot 3 ships with Micrometer; Prometheus and OpenTelemetry are first-class:

```yaml
management:
  tracing:
    sampling.probability: 1.0    # adjust per env
  otlp:
    tracing.endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT}
```

Per `observability`: trace context propagates via `traceId` / `spanId` MDC keys (configured in `logging.pattern` above).

## Testing

```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers
class OrderControllerIT {
    @Container static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16");
    
    @DynamicPropertySource
    static void dataSourceProps(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }

    @Autowired private TestRestTemplate rest;

    @Test
    void postCreatesOrder() {
        var res = rest.postForEntity("/api/orders", new OrderRequest(...), OrderResponse.class);
        assertThat(res.getStatusCode()).isEqualTo(HttpStatus.CREATED);
    }
}
```

Slice tests for faster feedback:
- `@WebMvcTest(OrderController.class)` — controller layer only
- `@DataJpaTest` — JPA layer only

## Native image (GraalVM) — when to consider

Spring Boot 3 + GraalVM Native Image gives ~50ms startup + 50MB memory at the cost of:
- Build time goes up dramatically
- Reflection requires hints
- Some libraries don't work natively
- Reduced runtime introspection

Use cases:
- Function-as-a-Service deployments (Lambda, Cloud Run, etc.) where cold start matters.
- Edge deployments where per-instance memory cost dominates.

Skip if you're running long-lived pods on K8s; JIT performance + ecosystem compatibility win.

## Common rationalizations

| Thought | Counter |
|---|---|
| "Field injection is faster to type." | Constructor injection is type-safe, test-friendly, and lambda-compatible. Use it. |
| "Lombok @Data on entities is fine." | JPA + Lombok @Data breaks equals/hashCode on lazy proxies. Use records for DTOs; explicit equality for entities. |
| "spring.jpa.hibernate.ddl-auto: update is convenient." | `update` ships schema drift to production. Validate-only + Flyway migrations. Mandatory. |
| "WebFlux scales better." | WebFlux scales differently. Reactive complexity is real; only adopt if profile demands it. |

## Official sources

- Spring Boot reference: https://docs.spring.io/spring-boot/docs/current/reference/html/
- Spring Data JPA: https://docs.spring.io/spring-data/jpa/docs/current/reference/html/
- Flyway: https://documentation.red-gate.com/fd
- Micrometer + Tracing: https://micrometer.io
- Testcontainers: https://testcontainers.com
