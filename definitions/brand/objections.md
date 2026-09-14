---
title: Objections
updated: 2026-09-14
---

What people push back on, and the honest answer. Never answer an objection by
denying it. Answer it by saying what is true.

## "This is just another dashboard."

A dashboard shows you a number. This one can tell you which tool it came from,
how many records went into it, and how many of those were missing the field.
When it moves, the history says whether the business changed or the definition
did. No dashboard answers that.

## "I don't trust AI with my numbers."

Neither do we. A fixed engine calculates every figure. The model is handed the
finished numbers, not the database, so it can word them and never invent them.
Every AI layer ships switched off.

## "We already have HubSpot and it has reports."

It has reports about HubSpot. The Acme in HubSpot, the Acme in Stripe and the
Acme in Zendesk are three records, and a report inside one tool cannot see the
other two. The joining is the product.

## "Setting this up sounds like a project."

It is one. Connecting a company's real accounts, agreeing what a customer is,
and getting the definitions to match how the business actually runs takes a
conversation, not a signup form. We say that up front because the alternative
is a churned customer in month two.

## "What happens when we outgrow it, or outgrow you?"

The code is yours under AGPL-3.0, in a repository you control, running on
Docker. The definitions are plain files. Nothing is held in our account.

## "Our data is a mess."

Yes. That is the starting condition, not a disqualifier. Raw records are kept
exactly as they arrived and everything is rebuilt from them, so a mess can be
re-derived correctly once you know what it should have been. Records that look
like the same customer but are not go to a review queue for a person to judge.

## "An AI agent opening pull requests sounds risky."

It never commits, never branches, and never approves itself. It reads a
restored copy of the database inside the runner, opens an issue with the
evidence, and stops. A person applies the label. Then a second agent writes
the change and a person merges it.

## "Why is it open source? What is the catch?"

The catch is that running it on your tools is the part we sell. The code being
readable is the reason a technical buyer trusts it at all.
