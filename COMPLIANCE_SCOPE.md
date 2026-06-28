# Compliance Scope

This document describes the extended compliance domain for future development of the MVP. It is based on `checklist-sites-domains-2026 (1).md` and `podrobny-razbor-zakonov-sayty-2026.md`.

The product remains a technical pre-check tool. It must not present findings as a legal conclusion, must not state that a site violates the law, and must keep manual review as the final confirmation step.

## Scope Areas

### Domain Identification

For domains in `.ru`, `.рф`, and `.su`, the compliance scope includes identifying whether the domain zone is covered by Russian domain administrator identification requirements. The relevant operational risks include inability to register, renew, transfer, change administrator, or update NS delegation if required identification is not completed.

Current MVP implication: `DomainComplianceAnalyzer` detects whether the domain zone is `.ru`, `.рф`, or `.su` and adds a manual-check recommendation for ESIA administrator identification. Administrator identity, registrar account status, actual ESIA identification status, and ownership history still require manual verification and are not checked by the MVP.

### User Authorization

The scope includes detecting signs of user authorization and identifying whether authentication depends on foreign providers such as Google, Apple, Facebook, Microsoft, or similar OAuth flows.

Allowed or lower-risk patterns may include local login/password, phone-based login, ESIA, and Russian authorization systems, but the MVP must report only technical evidence and avoid legal conclusions.

### Personal Data

The scope includes detecting forms and page elements that may collect personal data: name, phone, email, address, message text, company details, INN, and similar fields. It also includes checking for privacy-related documents and consent signals near forms.

The MVP can detect visible form and document signals. It cannot confirm the legal completeness of policy text, consent wording, retention periods, processing purposes, or internal operator procedures.

### Cookie Banner

The scope includes checking whether a site has a cookie banner or consent mechanism, especially when analytics, advertising pixels, chats, widgets, or other optional cookies are used.

The MVP now includes an optional Playwright-based `BrowserClient` infrastructure layer for collecting browser-observed cookies, network requests, visible text, and console errors when enabled. `CookieAnalyzer` uses that browser output to detect preliminary signs of a cookie banner, cookies after the initial page load before explicit user choice, and third-party analytics or advertising requests. The check is text-based, does not click buttons, does not submit forms, and does not make legal conclusions. Manual review remains required.

### Owner Requisites

The scope includes visible owner details on the site: legal name or full name, INN, OGRN or OGRNIP, address, contacts, and a dedicated contact channel for personal data subject requests where applicable.

The current MVP includes `OwnerRequisitesAnalyzer`, which detects visible organization/person names, INN, OGRN/OGRNIP, address-like text, phones, emails, and privacy-specific email contacts on crawled pages. It is a technical signal extractor and does not verify legal completeness of requisites.

### Personal Data Localization

The scope includes whether initial collection and storage of Russian citizens' personal data is performed using databases located in Russia.

This cannot be reliably confirmed from static HTML alone. Future support may analyze declared hosting, visible infrastructure hints, and user-provided hosting information, but final verification is expected to remain manual unless authoritative data is supplied.

### RKN Operator Notification

The scope includes whether the site owner/operator has submitted required notification to Roskomnadzor for personal data processing.

The current MVP does not query external registries or APIs. Future support may add a manual checklist field or offline evidence workflow. External API integration is outside the current MVP.

### Advertising And ERID

The scope includes internet advertising labeling: visible "advertising" markers, advertiser identification, and ERID tokens where applicable.

The current MVP does not classify advertising placements or verify ERID. Future static checks may detect obvious `erid` parameters and ad labels, with manual review for context.

### Accessibility

The scope includes baseline accessibility requirements such as text scaling, contrast, keyboard navigation, alt text, meaningful links/headings, and accessible CAPTCHA where applicable.

The current MVP does not perform accessibility analysis. Future checks should remain lightweight and static unless a later project phase explicitly allows browser-based tooling.

### Hosting

The scope includes whether hosting providers are listed in the relevant Russian hosting provider registry and whether the hosting provider identifies clients as required.

The current MVP does not verify hosting registry status. Future work may expose hosting hints and manual checklist fields without adding external APIs to the MVP.

### Russian Language

The scope includes detecting whether the site has Russian-language content or appears oriented toward Russian users.

The current MVP partially covers this through `RussianMarketAnalyzer`, which detects Russian-language and Russia-oriented technical signals.

### Social Networks And Channels Over 10,000 Subscribers

The scope includes identifying visible links to social networks, messengers, and public channels, and flagging the need to check whether channels/pages with 10,000 or more subscribers are registered in the RKN registry.

The current MVP can classify some social network and messenger links as external services, but it cannot determine subscriber counts or registry status. That remains a future/manual check.

## Out Of Scope For The Current MVP

The current MVP must not be expanded to include PostgreSQL, LLM, Telegram bot functionality, MCP, external registry APIs, background jobs, or persistent check history. Playwright is allowed only as an optional browser infrastructure layer controlled by settings; it must not introduce business logic, risk scoring, screenshots, form submission, or automatic consent actions.

Future analyzers should follow the existing layered architecture: analyzers work from `PageData` or explicit infrastructure outputs, services coordinate results, `RiskService` uses analyzer outputs only, and `ReportService` reports only facts present in `CheckResult`. Browser infrastructure should be used only where static HTML analysis is insufficient and must not contain compliance decisions.
