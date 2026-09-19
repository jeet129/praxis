# Engineering Standards — Java / Spring Boot

Stack-specific expression of the principles in `SKILL.md` for Java 17+ with Spring Boot 3.x.

## Project layout

Bounded contexts as top-level packages, not technical layers:

```
com.company.product.billing/
├── domain/             entities, value objects, aggregates, domain events
├── application/        use cases, application services, ports
├── infrastructure/     adapters (repository impls, external clients, persistence config)
└── presentation/       REST controllers, request/response DTOs

com.company.product.auth/
├── domain/
├── application/
├── infrastructure/
└── presentation/

com.company.product.shared/        # only truly cross-cutting concerns; default empty
├── common/
└── events/
```

`controllers/`, `services/`, `repositories/` as top-level packages is a violation — it organizes by mechanism rather than meaning.

## Naming

- Classes: `PascalCase`. Interfaces drop the `I` prefix — `OrderRepository` not `IOrderRepository`. The implementation carries a contextual name (`JpaOrderRepository`).
- Packages: lowercase, dotted, by domain concept.
- Methods: `camelCase`, verb-first: `chargeTenant`, `findActiveSubscriptions`.
- Constants: `SCREAMING_SNAKE_CASE`, declared `static final` in the most-local class that uses them. No `Constants.java` god-class.
- Booleans: `isActive`, `hasPermission`, `canRetry`.

## SOLID applied

**S — Single responsibility.** A class has one reason to change. The classic Spring violation is mixing controller + service + repository concerns in one class. Keep them separate.

**O — Open/closed.** Use interfaces or sealed classes for variation points; prefer composition over inheritance. Spring's strategy pattern (multiple beans implementing one interface, selected by `@Qualifier` or by type) is the canonical pattern.

**L — Liskov substitution.** Subtypes that throw on operations the supertype contract allows are violations. JPA's lazy-loading exceptions on detached entities are a common LSP trap — design the repository contract to forbid lazy access outside the transaction.

**I — Interface segregation.** Don't create kitchen-sink interfaces. `UserService` with 30 methods used in 30 different contexts is a violation. Split by use case.

**D — Dependency inversion.** Domain ports live in `domain/`; adapters in `infrastructure/`. The application service depends on the port interface, not the JPA repository directly. Spring's `@Component` + constructor injection makes this trivial.

## Error handling

- Catch narrow exceptions. `catch (DataAccessException e)` beats `catch (Exception e)`.
- Domain-typed exceptions extend a project-base `DomainException`. Infrastructure exceptions are translated at the application service boundary into domain exceptions.
- `@ControllerAdvice` translates domain exceptions to HTTP responses. The controller never builds error responses directly.
- `Optional<T>` for known-absent return types. Never return `null` for a `T` that should not be null.

## Validation

- Bean Validation (Jakarta Validation) at the API boundary on DTOs.
- Domain invariants in the constructor of domain objects — invalid state should be unconstructable.
- `@Valid` on controller method params; `@Validated` on service classes when method-level validation matters.

## Persistence

- JPA entities live in `infrastructure/persistence/` as adapters, not in `domain/`. Domain entities are pure; persistence entities are mapped from/to them.
- No `@OneToMany(fetch = FetchType.LAZY)` exposed past the application service — it leaks transaction scope. Either use DTOs at the boundary or eager-fetch where the use case demands.
- Migrations via Flyway or Liquibase, checked into the repo. `spring.jpa.hibernate.ddl-auto=update` in production is a blocker violation.

## Concurrency

- Avoid `synchronized` on instance methods; it's almost always wrong in Spring (singleton beans, multi-request concurrency). Use higher-level constructs.
- Database transactions are the canonical concurrency boundary. `@Transactional` on application service methods, never on controllers.
- For async work, use Spring's `@Async` with an explicit `ThreadPoolTaskExecutor` configured — never the default `SimpleAsyncTaskExecutor` in production.

## Logging

- SLF4J + Logback. `LoggerFactory.getLogger(MyClass.class)` per class.
- Structured logging via `net.logstash.logback` (`StructuredArguments.kv(...)`). String concatenation in log statements is a violation.
- Correlation ID via `MDC` — set by a `Filter` at the request boundary, cleared on completion.
- Never log full request bodies or response bodies that may carry PII.

## Build & packaging

- Maven or Gradle. Multi-module if the project has clear sub-systems; single-module if not (YAGNI — most projects don't need multi-module).
- Java toolchain version pinned (`<source>17</source>` etc.). Reproducible builds.
- Spring Boot uber-jar for deployable services. Distroless or Eclipse Temurin minimal base image; never the default JDK image in production.

## Testing

- JUnit 5 + AssertJ. No Hamcrest unless the team already standardized on it.
- Testcontainers for integration tests against real Postgres / Redis / Kafka — never embedded H2 as a Postgres substitute.
- Test class layout mirrors src: `src/test/java/.../billing/` for billing-domain tests.
- Test names: `methodUnderTest_givenCondition_expectedBehavior`. `placeOrder_whenTenantHasInsufficientCredit_throwsInsufficientFundsException`.

## Common violations to flag in review

- `@Autowired` on fields (use constructor injection).
- Static `getInstance()` in Spring-managed code (use beans).
- `RuntimeException` thrown without a domain meaning.
- `try { ... } catch (Exception e) { e.printStackTrace(); }` (swallowing + logging to stderr).
- Public mutable fields on domain entities (encapsulation violation).
- `System.out.println` anywhere outside a `main()`.
- N+1 query patterns in JPA mappings.
- `@Transactional` annotations on controllers or on private methods.

## Tooling

Recommended baseline:

- **Build:** Maven or Gradle (project chooses one).
- **Test:** JUnit 5, AssertJ, Mockito, Testcontainers.
- **Static analysis:** Checkstyle + SpotBugs + (optional) PMD; configured per project.
- **Code formatting:** Spotless with google-java-format.
- **Dependency hygiene:** Dependabot or Renovate; OWASP Dependency-Check in CI.
