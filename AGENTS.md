AGENTS.md
Purpose

This project should be developed with a strong focus on clean code, sound architecture, maintainability, reliability, security, and long-term simplicity.

All agents and developers working on this repository must follow the principles below.

Core Engineering Principles
1. Keep It Simple

Prefer simple solutions over clever solutions.

Do not introduce abstractions without a clear need.

Avoid unnecessary frameworks, dependencies, patterns, or layers.

Follow KISS — Keep It Simple, Stupid.

Solve the actual problem, not hypothetical future problems.

2. DRY — Don't Repeat Yourself

Avoid duplicated business logic.

Reuse well-defined functionality when it genuinely improves consistency.

Do not force unrelated code into a shared abstraction merely to remove a few duplicated lines.

Duplication is sometimes preferable to a bad abstraction.

3. SOLID Principles

Apply SOLID where appropriate:

Single Responsibility: A component should have one clear reason to change.

Open/Closed: Prefer designs that can be extended without unnecessarily modifying stable code.

Liskov Substitution: Implementations must honor the contracts of their abstractions.

Interface Segregation: Prefer small, focused interfaces.

Dependency Inversion: High-level business logic should not unnecessarily depend on low-level implementation details.

Do not apply SOLID mechanically. Practical simplicity is more important than theoretical purity.

4. Separation of Concerns

Keep responsibilities clearly separated.

For example:

Business logic should not depend directly on UI concerns.

Domain logic should not be tightly coupled to infrastructure.

Persistence logic should remain separate from business rules.

External API integrations should be isolated behind clear boundaries.

Configuration should not be scattered throughout the codebase.

5. Prefer Composition Over Inheritance

Use composition when it provides clearer and more flexible designs.

Avoid deep inheritance hierarchies unless inheritance genuinely represents the domain relationship.

6. Explicit Dependencies

Dependencies should be obvious.

Avoid:

Hidden global state

Unnecessary singletons

Implicit service dependencies

Excessive magic

Tight coupling

Prefer dependency injection or explicit construction where it improves testability and clarity.

Architecture
7. Define Clear Boundaries

Each module, package, or service should have a clear responsibility.

Dependencies should generally flow in one direction and should not create circular dependencies.

Before adding a new dependency between modules, ask:

Does this dependency make architectural sense, or am I taking a shortcut?

8. Protect the Domain

Business rules are core application logic.

Do not unnecessarily mix business rules with:

Database queries

HTTP handling

UI code

Serialization

Logging

Framework-specific concerns

Keep important business logic easy to test independently.

9. Avoid Premature Abstraction

Do not create:

Generic frameworks for one use case

Interfaces with only one trivial implementation

Factories that add no meaningful value

Layers that simply forward calls

Configuration systems for values that never change

Abstractions should solve a demonstrated problem.

10. Minimize Coupling

Prefer code that knows as little as reasonably possible about other components.

Changes in one area should have predictable and limited impact on unrelated areas.

Code Quality
11. Write Readable Code

Code should communicate intent clearly.

Prefer:

calculateTotal()


over:

process()


when the first name accurately describes the behavior.

Use meaningful names for:

Variables

Functions

Classes

Modules

APIs

Configuration values

Avoid unnecessary abbreviations.

12. Functions Should Be Focused

Prefer small functions with a clear purpose.

A function should generally:

Do one meaningful thing.

Have a clear input/output contract.

Avoid surprising side effects.

Be easy to test.

Do not split code into tiny functions merely to satisfy an arbitrary line-count rule.

13. Comments Explain Why

Prefer self-explanatory code.

Use comments when they explain:

Why something is implemented unusually

Important business rules

Non-obvious constraints

Workarounds for external systems

Performance or security considerations

Do not add comments that merely restate the code.

14. Error Handling

Handle errors deliberately.

Do not silently swallow errors.

Do not use exceptions for normal control flow unless appropriate for the language.

Preserve useful error context.

Return errors at appropriate architectural boundaries.

Never expose sensitive internal information to users.

Fail safely and predictably.

Testing
15. Tests Are Part of the Design

Write tests for important behavior, especially:

Business rules

Edge cases

Error handling

Public APIs

Security-sensitive functionality

Complex algorithms

Prefer tests that verify behavior rather than implementation details.

16. Test Pyramid

Prefer a healthy balance of:

Unit tests

Integration tests

End-to-end tests

Do not rely exclusively on expensive end-to-end tests.

17. Fix Tests With the Code

When changing behavior, update relevant tests.

Never weaken or delete a test merely because it exposes a bug unless the expected behavior has genuinely changed.

Security
18. Security by Default

Never:

Commit secrets, passwords, API keys, or tokens.

Log credentials or sensitive personal data.

Trust user input blindly.

Disable security controls merely to make development easier.

Construct database queries or shell commands unsafely.

Expose internal errors unnecessarily.

Validate input at system boundaries.

Use established security libraries and mechanisms instead of implementing cryptography or authentication primitives from scratch.

Dependencies
19. Minimize Dependencies

Before adding a dependency, consider:

Is it actually necessary?

Can the standard library solve the problem?

Is the dependency maintained?

Does it introduce significant complexity?

Does its license fit the project?

Does it create security or supply-chain risk?

Do not add a dependency for trivial functionality.

APIs and Interfaces
20. Design Stable Interfaces

Public APIs should be:

Explicit

Consistent

Predictable

Backward-compatible where required

Properly validated

Avoid leaking internal implementation details through public interfaces.

21. Backward Compatibility

Before changing an existing API, configuration format, database schema, or contract, determine:

Who depends on it?

What will break?

Is migration required?

Can compatibility be preserved?

Do not make breaking changes casually.

Database and Persistence
22. Treat Data Carefully

Database changes should consider:

Existing data

Migration safety

Rollback strategy

Indexes

Constraints

Transaction boundaries

Concurrency

Performance

Never assume a database is empty or disposable unless the project explicitly guarantees it.

23. Avoid Business Logic in Queries When It Hurts Maintainability

Keep complex business rules in appropriate application/domain layers unless there is a strong reason for database-side implementation.

Use the database's strengths for:

Constraints

Transactions

Aggregation

Indexing

Data integrity

Performance
24. Measure Before Optimizing

Do not optimize based solely on assumptions.

Prefer:

Correctness

Simplicity

Measurement

Targeted optimization

Avoid premature optimization that makes code significantly harder to understand.

25. Consider Scalability Where Relevant

For important code paths, consider:

Time complexity

Memory usage

Database queries

Network calls

Concurrency

Caching

Resource limits

Do not introduce distributed-system complexity without a real requirement.

Observability

Important systems should provide appropriate:

Logging

Metrics

Tracing

Health checks

Error reporting

Logs should be useful for debugging without exposing secrets or sensitive information.

Git and Changes
26. Keep Changes Focused

Each change should have a clear purpose.

Avoid mixing:

Refactoring

Feature development

Unrelated formatting

Dependency upgrades

Bug fixes

into one unnecessarily large change.

27. Preserve Existing Behavior

Before modifying code, understand what it currently does.

Do not rewrite working components merely because another implementation looks cleaner unless there is a clear benefit.

28. Review Your Own Changes

Before considering work complete:

Read the diff.

Remove accidental changes.

Check error paths.

Check edge cases.

Run relevant tests.

Check formatting and linting.

Look for security issues.

Consider backwards compatibility.

Working With Existing Code

Before implementing a change:

Understand the existing architecture.

Find the relevant modules and entry points.

Identify existing patterns.

Reuse existing conventions.

Check existing tests.

Understand dependencies and side effects.

Make the smallest clean change that solves the problem.

Do not introduce a completely new pattern when the codebase already has an established, appropriate pattern.

Refactoring

Refactoring should improve the code without changing externally observable behavior unless explicitly intended.

Good refactoring:

Reduces complexity.

Improves naming.

Removes duplication.

Clarifies responsibilities.

Reduces coupling.

Improves testability.

Avoid refactoring unrelated code simply because you are already touching a file.

Decision Making

When multiple solutions are possible, prefer the solution that provides the best balance of:

Correctness

Simplicity

Maintainability

Testability

Security

Performance

Extensibility

Do not optimize for theoretical elegance at the expense of practical maintainability.

Agent Rules

When working on this repository, agents MUST:

Understand before modifying.

Follow existing project conventions.

Keep changes focused.

Prefer simple designs.

Avoid unnecessary abstractions.

Preserve existing behavior unless change is intentional.

Add or update tests for meaningful behavior changes.

Run relevant tests and validation.

Consider security implications.

Consider error handling and edge cases.

Review the final diff.

Clearly communicate important assumptions and trade-offs.

Agents MUST NOT:

Introduce unnecessary dependencies.

Add speculative architecture.

Ignore failing tests without explanation.

Hide errors.

Commit secrets.

Make unrelated changes.

Rewrite large portions of the codebase without justification.

Remove functionality without understanding its consumers.

Sacrifice maintainability for short-term convenience.

Definition of Done

A change is not complete merely because it compiles.

Before considering a task complete, verify:

 The implementation solves the requested problem.

 The design fits the existing architecture.

 Responsibilities are appropriately separated.

 Code is readable and maintainable.

 Error cases are handled.

 Security implications have been considered.

 Tests have been added or updated where appropriate.

 Relevant tests pass.

 Formatting/linting/static analysis pass where applicable.

 No unnecessary dependencies or abstractions were introduced.

 No unrelated files were changed.

 The final diff has been reviewed.

Guiding Principle

Build software that is boring in the best possible way: simple to understand, difficult to misuse, easy to test, safe to change, and reliable in production.

When in doubt, choose clarity over cleverness, simplicity over complexity, explicitness over magic, and maintainability over short-term convenience.
