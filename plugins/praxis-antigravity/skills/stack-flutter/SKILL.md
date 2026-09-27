---
name: stack-flutter
description: "Idiomatic Flutter/Dart mobile implementation pack — project layout (feature-first + clean architecture), state management (Riverpod / Bloc), strict analyzer + null-safety, navigation (go_router), networking (dio + retrofit + generated OpenAPI clients), local persistence (Drift / Isar / secure storage), streaming-audio + WebSocket/SSE patterns for a voice-first UI, accessibility via the Semantics API, senior-first UI constraints (large type, high contrast, low tap-count), performance budgets for low-end Android, and test idioms (unit + widget + golden + integration). Complements `engineering-standards` (the bar) with mobile implementation idioms (the playbook). Use whenever a developer is implementing a Flutter mobile slice, scaffolding the app, wiring a streaming voice surface, or choosing between mobile state-management patterns."
---

# Stack — Flutter (Dart)

<!-- praxis:metadata:begin -->
```yaml
capability: stack
domain: frontend
state: active
dependencies:
 - engineering-standards
triggers:
 - "implementing a feature on Flutter"
 - "scaffolding the Flutter mobile app"
 - "choosing between Riverpod / Bloc"
 - "wiring a streaming voice / audio UI"
 - "configuring the Dart analyzer / null-safety"
 - "setting mobile performance or accessibility budgets"
 - "configuring Flutter testing (widget / golden / integration)"
outputs:
 - scaffolded feature module conforming to the layout
 - code conforming to standards + Flutter idioms
 - pubspec.yaml + pinned dependency set
 - generated API clients from OpenAPI contracts
 - widget + golden + integration test scaffolds
consumers:
 - frontend-developer
 - ux-designer
 - code-review
 - testing-strategy
 - accessibility
references:
 - riverpod.md
 - streaming-voice.md
 - senior-first-ui.md
```
<!-- praxis:metadata:end -->

Implementation idioms for Flutter 3.x / Dart 3.x mobile apps. Complements `engineering-standards` — that is the *bar*; this file is the *playbook*. This pack exists because the web-frontend pack (`stack-web-frontend`) assumes a browser runtime (Lighthouse, Core Web Vitals, bundle budgets, DOM a11y) that does not map to a compiled mobile client. Use this pack for the consumer mobile app; use `stack-web-frontend` only for web surfaces (e.g. a creator/admin console).

## When this pack applies

Mobile client work: the Android/iOS consumer app, the senior-first design-system components, and the voice-first conversational surface. Targets **low-end Android (₹8–10K devices, Android 9+)** as the primary constraint — performance and accessibility budgets are set for that hardware, not flagships.

## Framework / state-management choice

| Choice | Sweet spot | Reference |
|---|---|---|
| **Riverpod 2.x** | Default. Compile-safe DI + state, testable without widgets, good async primitives (`AsyncValue`, `StreamProvider`) for streaming UIs. | `references/riverpod.md` |
| **Bloc / Cubit** | When the team prefers explicit event→state machines and strict separation; heavier boilerplate. | — |
| **setState only** | Local, ephemeral widget state only. Never app/business state. | — |

Default: **Riverpod** unless the team has a standing Bloc convention. Pick once, in an ADR, before building the design system (M03).

## Project layout — feature-first + clean architecture

```
lib/
├── main.dart                      composition root (ProviderScope)
├── app/                           MaterialApp, theme, router, localization wiring
│  ├── app.dart
│  ├── theme/                      design tokens (from M03 design-system)
│  └── router.dart                 go_router config
├── core/                          cross-cutting (no feature deps)
│  ├── network/                    dio client, interceptors, auth, retry
│  ├── error/                      Failure types, error mapping
│  ├── accessibility/              Semantics helpers, text-scale clamps
│  └── audio/                      streaming player + STT/TTS adapters
├── features/
│  └── saathi/                     one feature = one folder (mirrors a module/slice)
│     ├── domain/                  entities, value objects, repository interfaces
│     ├── data/                    repository impls, dtos (json_serializable), datasources
│     └── presentation/            screens, widgets, controllers (Riverpod notifiers)
├── shared/                        shared widgets (design-system components)
└── l10n/                          ARB files per locale (intl)

test/        mirrors lib/   (unit + widget)
test/golden/ golden image tests for design-system components
integration_test/             end-to-end on device/emulator
```

Feature-first keeps each slice's UI + data + domain together; `core/` and `shared/` hold only cross-cutting code. `domain/` never imports `data/` or Flutter — dependency inversion via repository interfaces.

## Dependency management

`pubspec.yaml` with pinned constraints; `pubspec.lock` checked in. Baseline set:

```yaml
dependencies:
  flutter: { sdk: flutter }
  flutter_localizations: { sdk: flutter }
  flutter_riverpod: ^2.5.0
  riverpod_annotation: ^2.3.0
  go_router: ^14.0.0
  dio: ^5.4.0
  retrofit: ^4.1.0
  json_annotation: ^4.9.0
  freezed_annotation: ^2.4.0
  drift: ^2.16.0                 # local relational cache (or isar)
  flutter_secure_storage: ^9.0.0 # tokens / secrets only
  intl: ^0.19.0

dev_dependencies:
  build_runner: ^2.4.0
  riverpod_generator: ^2.4.0
  retrofit_generator: ^8.1.0
  json_serializable: ^6.8.0
  freezed: ^2.5.0
  very_good_analysis: ^6.0.0    # strict lint preset
  flutter_test: { sdk: flutter }
  golden_toolkit: ^0.15.0
  integration_test: { sdk: flutter }
```

Pin the Flutter/Dart SDK in `pubspec.yaml` `environment:` and an `.fvmrc` (FVM) so every machine + CI builds the same toolchain.

## Analyzer — strict by default

`analysis_options.yaml`:

```yaml
include: package:very_good_analysis/analysis_options.yaml
analyzer:
  language:
    strict-casts: true
    strict-inference: true
    strict-raw-types: true
  errors:
    invalid_annotation_target: ignore
linter:
  rules:
    prefer_const_constructors: true
    avoid_print: true
    require_trailing_commas: true
```

Null-safety is non-negotiable. Treat analyzer warnings as CI failures.

## Boundary types — freezed + json_serializable

Immutable models with generated equality, copyWith, and JSON. Generate DTOs from the OpenAPI contracts in `contracts/` rather than hand-writing them.

```dart
@freezed
class SaathiTurn with _$SaathiTurn {
  const factory SaathiTurn({
    required String id,            // ULID from the shared id scheme
    required SaathiRole role,
    required String text,
    @Default(SafetyVerdict.allowed) SafetyVerdict safety,
  }) = _SaathiTurn;

  factory SaathiTurn.fromJson(Map<String, dynamic> json) =>
      _$SaathiTurnFromJson(json);
}
```

## State — Riverpod notifier

```dart
@riverpod
class SaathiController extends _$SaathiController {
  @override
  FutureOr<List<SaathiTurn>> build() => [];

  Future<void> send(String utterance) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      final repo = ref.read(saathiRepositoryProvider);
      return repo.send(utterance);
    });
  }
}
```

`AsyncValue` models loading/data/error in one type — the UI renders all three states explicitly; no silent spinners that never resolve.

## Streaming voice surface

The conversational surface streams audio in, captions + agent tokens out. Patterns:

- Use a **WebSocket or SSE** channel exposed as a Dart `Stream`, surfaced via `StreamProvider`. Keep the socket in `core/audio/`; the feature consumes the stream, never the raw socket.
- **Render captions incrementally** as tokens arrive; do not wait for the full turn.
- **Safety gate is authoritative.** Every inbound utterance and outbound response is mediated by the moderation service. The client must render the *human-handoff* path (medical/legal/financial intents routed to a person) as a first-class state — never fabricate or display a generative answer for those intents.
- **Graceful degradation:** detect poor connectivity and fall back to audio-only / push-to-talk; show a calm, explicit "reconnecting" state rather than freezing.
- **Barge-in + lifecycle:** stop playback/capture on `AppLifecycleState.paused`; release audio focus; cancel the stream subscription in `dispose`.

See `references/streaming-voice.md`.

## Senior-first UI constraints (encode once, inherit everywhere)

These are product requirements, not preferences — they live in the design-system components (M03) so every screen inherits them:

- **Type:** base body ≥ 18pt; respect OS text scaling and clamp to a sane max so layouts don't break at 200%.
- **Contrast:** WCAG AA+ for all text and interactive elements.
- **Tap targets:** ≥ 48×48 dp; primary actions reachable in ≤ 3 taps.
- **Audio-first:** every key screen has an audio readout path; controls have `Semantics` labels in the active locale.
- **Indic scripts:** use bundled Noto fonts; verify rendering at large sizes across Tamil/Bengali/Devanagari/etc. — do not rely on OEM system fonts.

## Accessibility — Semantics API

```dart
Semantics(
  label: l10n.playDailyRitual,   // localized, not hard-coded English
  button: true,
  child: IconButton(onPressed: _play, icon: const Icon(Icons.play_arrow)),
);
```

Test with TalkBack; cover the audio-readout flow in `integration_test/`. Accessibility is verified, not assumed — see the `accessibility` skill.

## Performance budgets (low-end Android)

- **Cold start** to first interactive ≤ 2.5s on a reference ₹8–10K device.
- **Jank:** maintain 60fps on scroll; no frame > 16ms on the daily-ritual and Saathi screens. Profile with DevTools timeline in **profile mode** (never debug-mode numbers).
- **Memory:** avoid retaining decoded images; use `cacheWidth`/`cacheHeight`; dispose controllers and stream subscriptions.
- **App size:** ship split-per-ABI / app bundle; track download size as a budget. Defer heavy assets.
- **Build `const` aggressively;** avoid rebuilding subtrees — scope `ref.watch` to the smallest provider.

## Testing

pyramid: unit (domain + controllers) → widget → golden (design-system components) → integration (critical journeys on emulator).

```dart
testWidgets('renders human-handoff state for medical intent', (tester) async {
  await tester.pumpWidget(ProviderScope(
    overrides: [saathiRepositoryProvider.overrideWithValue(FakeSaathiRepo.medical())],
    child: const SaathiScreen(),
  ));
  await tester.pumpAndSettle();
  expect(find.byKey(const Key('human-handoff-card')), findsOneWidget);
  expect(find.byKey(const Key('generative-answer')), findsNothing);
});
```

Golden tests lock the senior-first visual rules (type size, contrast, spacing). Run integration tests in CI on an emulator matrix.

## Build, release & CI

- **Flavors:** `dev` / `staging` / `prod` with per-flavor config; never hard-code endpoints.
- **CI:** `flutter analyze` → `flutter test` → `flutter test --tags golden` → build appbundle. Fail on analyzer warnings.
- **Release automation:** Fastlane for Play/App Store; signing keys in CI secrets, never in the repo.
- **Crash + RUM:** wire Sentry/Firebase Crashlytics + lightweight performance traces; surface to the same observability backend as the services.

## Mode handling (G/B)

**Greenfield.** `flutter create` with the feature-first layout from the start; set up Riverpod, go_router, analyzer, and the design-system package before the first feature slice.

**Brownfield.** Read `.repo-intel/conventions.md`; match the existing state-management choice for new code rather than introducing a second one; flag any divergence in an ADR.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "I'll use `stack-web-frontend` for the mobile app — frontend is frontend." | Web budgets (Lighthouse, Core Web Vitals, bundle size) don't exist on a compiled mobile client. Mobile has its own budgets: cold start, jank, app size, battery. Use this pack. |
| "setState is simpler than Riverpod." | setState is fine for *local ephemeral* widget state. App/business/async state in setState becomes untestable and leaks across rebuilds. |
| "Hard-code the English label; we'll localize later." | The audience is vernacular-first. Strings ship through `intl`/ARB and `Semantics` labels from day one, or the a11y + i18n gates fail. |
| "Skip golden tests; widget tests are enough." | The senior-first rules (type size, contrast, spacing) are *visual* contracts. Only golden tests catch a regression that shrinks body text below 18pt. |
| "Render the model's answer; moderation can run server-side." | The client must render the human-handoff path as a first-class state. Displaying a generative answer for a medical/legal/financial intent is a safety violation, not a UI shortcut. |
| "Profile-mode/debug numbers are close enough." | Debug builds are 5–10x slower and misleading. Performance budgets are measured in profile mode on a real low-end device. |
| "Test on the emulator / my flagship; it's smooth." | The product constraint is ₹8–10K Android. Smooth on a Pixel says nothing about the target device. Keep a reference low-end device in the loop. |

## Verification

You are done when:

- [ ] `flutter analyze` runs clean with the strict preset (warnings = failures).
- [ ] State management is the chosen pattern (Riverpod/Bloc) — no stray app-state in setState.
- [ ] `pubspec.lock` checked in; Flutter/Dart SDK pinned (FVM/`environment:`).
- [ ] DTOs generated from the `contracts/` OpenAPI specs, not hand-written.
- [ ] Every interactive element has a localized `Semantics` label; TalkBack flow tested.
- [ ] Senior-first budgets met: body ≥ 18pt, AA+ contrast, ≥48dp targets, ≤3 taps to primary action.
- [ ] Streaming surface renders loading/data/error + human-handoff states explicitly and degrades gracefully offline.
- [ ] Golden tests cover design-system components; widget + integration tests cover critical journeys.
- [ ] Performance budgets checked in **profile mode** on a reference low-end Android device.
- [ ] Brownfield: existing conventions matched; divergence captured in an ADR.

Evidence to check:
- CI log shows `flutter analyze` + `flutter test` + golden + integration green.
- DevTools profile-mode timeline on the reference device shows cold start ≤ 2.5s and no >16ms frames on key screens.
- A11y scan / manual TalkBack pass recorded for the daily-ritual and Saathi screens.

## Anti-patterns

- Using `stack-web-frontend` budgets/tooling for the mobile app.
- App/business state in `setState`; business logic inside widgets.
- `domain/` importing `data/` or Flutter (dependency-inversion violation).
- Hard-coded user-facing strings; missing `Semantics` labels.
- Blocking the UI isolate with heavy JSON/image work (use isolates / `compute`).
- Not disposing controllers, `StreamSubscription`s, or audio focus.
- Measuring performance in debug mode; testing only on flagships/emulators.
- Hand-written API models that drift from the `contracts/` source of truth.
- Rendering a generative answer for medical/legal/financial intents instead of the human-handoff path.
