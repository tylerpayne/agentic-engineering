---
name: plain-english
description: Write in plain, declarative English without AI-sounding rhetorical patterns. Use for all prose, always. Applies to every kind of writing: design docs, RFCs, architecture decision records, paper abstracts, API and library documentation, READMEs, code comments, commit messages, PR descriptions, incident write-ups, research notes, reports, memos, emails, and any other written output. These rules apply to technical writing as much as to any other kind. Also use when the user says a draft sounds like AI, sounds like slop, is too punchy, or does not sound like them.
---

# Plain English

These are rules about sentence construction, punctuation, and cadence, and they
apply to every kind of prose regardless of subject.

Headings, list items, table cells, checklists, and the Bad and Good pairs below
are apparatus rather than prose, so the rules about sentence length and fragments
do not apply to them. Figures inside an example are illustrative and carry no
claim about the world.

Test every draft by reading it aloud, flatly, with no emphasis anywhere. Rewrite
any sentence that needs a performed pause to work.

## Banned constructions

**Negate-then-assert.** Never introduce a wrong version in order to refute
it. The forms include "not X, it is Y", "X isn't about A, it's about B", and
"this doesn't just P, it Q's".

- Bad: "This doesn't just fix the leak, it restructures ownership."
- Good: "This restructures buffer ownership, which fixes the leak."

**Fragments for effect.** Never add a short sentence after a long one for
emphasis. The test is what the short sentence carries rather than how long it is.
Rhetoric restates or answers the sentence before it. A normal sentence reports a
new fact, and it may be as short as the fact requires.

- Bad: "The models complete every task. All of them."
- Good: "The models complete all 240 tasks."
- Allowed: "The build failed." Nothing precedes it that it restates.

**Contrast hidden in a subordinate clause.** Never put the real point in a
"while", "even as", "despite", or "although" clause. Put the point in the main
clause and drop whatever is left.

- Bad: "The models complete every task while failing style checks on 40% of them."
- Good: "The models fail style checks on 40% of completed tasks."

**Rhetorical reversal.** Never mirror an earlier phrase back on itself. This
includes the trailing "or won't", "or doesn't", and "and wasn't", used with no new
predicate. Keep a second clause when it adds a real condition.

- Bad: "The cache either solves the latency problem, or it doesn't."
- Good: "The cache helps only when the working set fits in memory."

**Restating identity for emphasis.** Say the one thing you mean once. "The
frontier of X and the frontier of Y are the same frontier" and "the best
abstraction is no abstraction" both say it twice.

**Telling instead of showing.** Never claim the quality, scale, or thoroughness of
what you are describing. Give the specifics that would justify the claim. When you
do not have the specific figure, name the mechanism. Never invent a number to
satisfy this rule.

- Bad: "The migration was a massive undertaking involving extensive refactoring."
- Good: "The migration touched 340 files and replaced three storage backends with one."
- Good, with no measurement to hand: "The migration replaced three storage backends with one."

**Defining by negation.** Never define a thing by what it is not. Describe what
it is. This appears most often in documentation, where the writer anticipates a
wrong guess and answers it instead of stating the behavior.

- Bad: "This is not a full ORM."
- Good: "This maps rows to structs and generates SELECT and INSERT statements."
- Bad: "Unlike a mutex, this does not block the calling thread."
- Good: "The write completes in the background and the calling thread continues."

State a negative when the negative is itself the guarantee. Thread safety,
ordering, durability, idempotency, retry behavior, and scope limits are contracts
a caller relies on, and a positive rewrite drops the half that matters.

- Keep: "The queue guarantees ordering within a partition and gives no ordering guarantee across partitions."
- Keep: "This type is not thread-safe."
- Keep: "The client does not retry on 5xx."

**Borrowed metaphors.** Never borrow a verb from an unrelated domain when the
literal one exists. Money metaphors are the most common kind. Phrases like "you
pay for that in latency", "a tax on readability", "the cost of this abstraction",
"buys us headroom", and "the budget for complexity" appear where nothing is being
paid, taxed, bought, or budgeted.

- Bad: "Every rhetorical move the reader has to see through is a tax on comprehension."
- Good: "Rhetorical patterns slow comprehension."
- Bad: "You pay for the extra indirection in cache misses."
- Good: "The extra indirection causes cache misses."

The pattern generalizes past money. Ban borrowed metaphors of every kind,
including unlock, supercharge, turbocharge, double down, move the needle, north
star, secret sauce, Swiss army knife, battle-tested, bread and butter, heavy
lifting, low-hanging fruit, the beating heart of, lives at the intersection of,
journey, landscape, ecosystem, and any war, sports, or weather figure standing in
for a plain verb. A metaphor is justified only when no literal term exists and it
names the thing precisely.

Keep genuine terms of art. Cost, budget, and overhead are literal when the thing
measured is money, time, memory, or tokens, and the words cache, queue,
backpressure, backoff, eviction, starvation, circuit breaker, poison pill, and
watchdog name the things themselves.

**Adjective stacks.** Strings of evaluative adjectives stand in for a number, a
name, or a mechanism that would say it precisely.

- Bad: "a rigorous, comprehensive, deeply technical test suite"
- Good: "1,400 tests covering every public method"

## Punctuation

- Use a comma, a period, or a restructured sentence in place of any em dash.
- Never use a mid-sentence colon to define a term, introduce an example, or add
  emphasis. Colons work in a title, and before a genuine list of items.
- Never use `·` or other decorative separators in prose.
- Keep real content out of parentheticals. Promote it to a clause, or cut it. A
  parenthetical may carry an "e.g." list of no more than three items (e.g. todo,
  doing, done).
- Never write "i.e." at all, inside parentheses or after a comma. An "i.e." gloss
  means the sentence before it failed to say the thing, so rewrite that sentence.

## Sentence shape

Long sentences are fine when the length carries content.

Prefer one long declarative sentence with concrete clauses joined by "and" over
three short ones arranged for rhythm.

> The indexer walks the changed files, resolves each import against the module
> graph, writes one row per symbol into the local database, and invalidates
> downstream entries for moved symbols.

Keep the subject short, because a subject weighed down by a relative clause makes
the reader hold everything until the verb arrives, so "every rhetorical move the
reader has to see through" becomes "rhetorical patterns" unless the qualifier is
essential. Cut "that", "which", and "who" clauses wherever the plain noun says
it.

Vary sentence length only as the content requires, never to create a rhythm. Avoid
opening consecutive sentences with the same structure. Do not shorten a closing
sentence for effect.

## Word choice

- Prefer concrete nouns to abstractions. Write "the retry loop" rather than "the
  resilience layer", and "the Postgres table" rather than "the persistence tier".
  Name the thing a reader could point at in the code.
- Repeat a plain word across sentences instead of reaching for a synonym.
- Cut words the verb already carries. "Failing the correctness check" says
  correctness twice, so name the check that ran. The same goes for
  "successfully completed", "collaborate together", and "merge together".
- Cut intensifiers such as "deeply", "truly", "fundamentally", "incredibly",
  "seamlessly", and "robustly".
- Use one hedge at most. "May potentially" and "could possibly help to" stack them.
- Do not capitalize an internal project name as though the reader knows it.
  Describe it.

## Checklist

One item per rule above, worded to stand on its own. Run all of it against a
finished draft, then read the draft aloud flatly and rewrite any sentence that
needs a performed pause to work.

Banned constructions

- "not X, it is Y" in any form
- a short sentence that restates or answers the one before it rather than
  reporting a new fact
- a "while", "despite", or "although" clause holding the real point
- a phrase mirrored back on itself with no new predicate
- the same point stated twice as an identity
- claims about quality, scale, or effort
- a number that was invented to replace such a claim
- a thing defined by what it is not, except where the negative is itself the
  guarantee, covering thread safety, ordering, durability, idempotency, retry
  behavior, and scope limits
- metaphors where a literal verb exists, especially paying, taxing, or buying
- adjectives standing in for numbers or mechanisms

Punctuation

- em dashes
- any mid-sentence colon that defines or emphasizes
- decorative `·` and similar separators
- parentheticals holding real content, allowing only an "e.g." list of three
  items or fewer
- "i.e." anywhere, parenthesized or not

Sentence shape

- three short sentences where one long one carries the content
- a subject buried under a relative clause
- "that", "which", or "who" clauses the plain noun makes unnecessary
- consecutive sentences opening with the same structure
- a closing sentence shortened for effect
- sentence length varied for rhythm rather than for content

Word choice

- abstractions where a concrete noun exists
- a synonym reached for in place of repeating the plain word
- words the verb already carries
- intensifiers
- more than one hedge
- an internal project name capitalized and left undescribed
