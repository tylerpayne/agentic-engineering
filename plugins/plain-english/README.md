# plain-english

A skill that constrains how Claude writes prose. It bans the sentence shapes,
punctuation, and cadence that make text read as machine-generated, and it applies
to every kind of writing rather than to a particular document type.

## Install

```bash
claude plugin marketplace add tylerpayne/claude-code-plugins
claude plugin install plain-english@tylerpayne
```

## What it changes

The skill covers four areas.

**Banned constructions.** Negate-then-assert ("not X, it is Y"), a short sentence
that only restates the one before it, a real point parked in a "while" or
"despite" clause, phrases mirrored back on themselves, claims about the quality or
scale of the work, definitions written as what something is not, borrowed
metaphors such as paying or taxing or unlocking, and stacks of evaluative
adjectives.

Two carve-outs keep the rules from damaging technical writing. A negative stands
when the negative is itself the guarantee, so "not thread-safe" and "does not
retry on 5xx" survive. Replacing a vague quality claim with a specific figure
requires having the figure, and the skill says to name the mechanism rather than
invent a number.

**Punctuation.** No em dashes, no mid-sentence colon that defines a term or
introduces an example, and no decorative separators. Parentheticals hold no real
content, except an "e.g." list of three items or fewer (e.g. todo, doing, done).
"i.e." is banned everywhere, parenthesized or not, because the gloss means the
preceding sentence should have said the thing.

**Sentence shape.** One long declarative sentence with concrete clauses beats
three short ones arranged for rhythm. Sentence length varies with content rather
than to create a beat.

**Word choice.** Concrete nouns over abstractions, the same plain word repeated
instead of a synonym, no intensifiers, and one hedge at most.

The skill ends with a checklist derived from the rules, one item each, to run
against a finished draft.

## When it activates

The description tells Claude to use it for all prose, always. It also fires when
you say a draft sounds like AI, sounds like slop, is too punchy, or does not
sound like you.

To apply it to an existing draft, ask for a pass over the file by name.
