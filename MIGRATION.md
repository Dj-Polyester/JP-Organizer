# Version 1.0.1

Modify the existing **jp-organizer** project. The project is already implemented and working. This is a targeted migration of the vocabulary classification/deck model, not a rewrite.

Before changing code, inspect:

* the existing implementation;
* existing tests;
* `README.md`;
* `TASK.md`;
* the current JMdict indexer/schema;
* the current JMdict POS mappings;
* the actual JMdict semantic/miscellaneous entity mappings available in the dictionary data.

Preserve working functionality that is unrelated to this change.

# 1. New deck structure

Change the permanent managed Anki hierarchy to:

```text
Japanese
├── Vocabulary
│   ├── Words
│   ├── Mimetics
│   ├── Expressions
│   │   ├── Constructions
│   │   ├── Idioms
│   │   └── Collocations
│   └── Other
└── Kanji
```

Leaf decks:

```text
Japanese::Vocabulary::Words
Japanese::Vocabulary::Mimetics
Japanese::Vocabulary::Expressions::Constructions
Japanese::Vocabulary::Expressions::Idioms
Japanese::Vocabulary::Expressions::Collocations
Japanese::Vocabulary::Other
Japanese::Kanji
```

`Japanese::Vocabulary` and `Japanese::Vocabulary::Expressions` are grouping decks only.

Managed vocabulary cards must live in exactly one vocabulary leaf deck.

# 2. Mutually exclusive primary class

Every managed vocabulary entry must have exactly one:

```text
primary_class
```

Allowed values:

```text
word
mimetic
construction
idiom
collocation
other
```

Mapping:

```text
word
→ Japanese::Vocabulary::Words

mimetic
→ Japanese::Vocabulary::Mimetics

construction
→ Japanese::Vocabulary::Expressions::Constructions

idiom
→ Japanese::Vocabulary::Expressions::Idioms

collocation
→ Japanese::Vocabulary::Expressions::Collocations

other
→ Japanese::Vocabulary::Other
```

The invariant is:

```text
one source vocabulary item
        ↓
one managed vocabulary note
        ↓
one primary_class
        ↓
one vocabulary leaf deck
        ↓
one vocabulary kind tag
```

Never create duplicate vocabulary notes to represent multiple classifications.

When classification changes, MOVE the existing managed card to the new leaf deck.

# 3. Kind tags

Replace the old generic vocabulary tag:

```text
jp-organizer::kind::vocabulary
```

with mutually exclusive kind tags:

```text
jp-organizer::kind::word
jp-organizer::kind::mimetic
jp-organizer::kind::expression::construction
jp-organizer::kind::expression::idiom
jp-organizer::kind::expression::collocation
jp-organizer::kind::other
```

Kanji continues to use:

```text
jp-organizer::kind::kanji
```

Every managed vocabulary note must have exactly one vocabulary kind tag.

The kind tag must always agree with:

```text
primary_class
```

and with the note's vocabulary leaf deck.

# 4. POS classification remains independent and JMdict-based

Do NOT change the source or behavior of POS classification.

POS classification remains deterministic and is derived from JMdict for **all vocabulary items**, regardless of their `primary_class`.

Keep:

```text
jp-organizer::pos::noun
jp-organizer::pos::verb
jp-organizer::pos::adjective
jp-organizer::pos::adverb
jp-organizer::pos::other
```

POS tags and kind/deck classification are independent dimensions.

Conceptually:

```text
primary_class
    ↓
controls deck + kind tag

JMdict POS
    ↓
controls pos::* tags
```

Do not use `primary_class` to suppress POS tags.

Examples:

```text
食べる

primary_class:
word

deck:
Japanese::Vocabulary::Words

tags:
jp-organizer::kind::word
jp-organizer::pos::verb
```

A mimetic can still have ordinary POS information:

```text
ぐっすり

primary_class:
mimetic

deck:
Japanese::Vocabulary::Mimetics

tags:
jp-organizer::kind::mimetic
jp-organizer::pos::adverb
```

An idiom or collocation may likewise retain any POS tags legitimately returned by the existing JMdict classification logic.

Do not infer POS from the semantic class.

The LLM must never invent POS tags.

POS continues to come only from JMdict.

If no simplified noun/verb/adjective/adverb classification applies under the existing JMdict mapping, continue using:

```text
jp-organizer::pos::other
```

according to the project's existing POS rules.

# 5. Kind and POS are intentionally orthogonal

The new design must explicitly distinguish these two concepts.

For example:

```text
ぐっすり
```

can simultaneously be:

```text
kind:
mimetic

POS:
adverb
```

This is valid because the meanings are different:

```text
kind
→ what vocabulary study class/deck the item belongs to

POS
→ grammatical information provided by JMdict
```

Likewise:

```text
顔が広い
```

may have:

```text
kind:
expression::idiom
```

while also retaining whatever POS classification the project's JMdict lookup legitimately derives.

Do not attempt to make POS mutually exclusive with the vocabulary deck classes.

Only `kind` / `primary_class` is mutually exclusive.

# 6. Semantic classification must be JMdict-first

Change the existing semantic-classification pipeline.

Semantic classes are:

```text
mimetic
construction
idiom
collocation
none
```

The system must FIRST attempt to determine semantic classification from JMdict.

Only when JMdict cannot provide a sufficiently specific classification should it ask the OpenCode/client LLM.

Architecture:

```text
Vocabulary entry
       │
       ▼
JMdict SQLite lookup
       │
       ├── POS metadata
       │      ↓
       │   POS tags
       │
       └── semantic-relevant metadata
              ↓
       decisive semantic classification?
              │
        ┌─────┴─────┐
        │           │
       yes          no
        │           │
        ▼           ▼
   use JMdict     ask client LLM
        │           │
        └─────┬─────┘
              ▼
        primary_class
```

POS lookup and semantic lookup are independent products of the JMdict lookup.

# 7. Inspect actual JMdict semantic entities

Do not hardcode assumptions solely from this specification.

Inspect the actual JMdict entity definitions/data used by the project and determine which metadata can directly support:

```text
mimetic
construction
idiom
collocation
```

Known examples in JMdict include entities corresponding to concepts such as:

```text
onomatopoeic or mimetic word
idiomatic expression
expression / phrase / clause
```

Use the actual entity codes present in the supplied/current JMdict data.

For example, if the current dictionary contains codes equivalent to:

```text
on-mim
id
exp
```

inspect and use their actual semantics.

Centralize semantic mappings in one module.

Conceptually:

```text
raw JMdict semantic metadata
        ↓
JMdict semantic mapper
        ↓
mimetic / idiom / unresolved-expression / none
```

Do not scatter JMdict semantic-code checks throughout the project.

# 8. Only use JMdict semantic classification when sufficiently specific

JMdict-first does NOT mean forcing all semantic classifications from JMdict.

Only use a JMdict semantic marker when it directly and sufficiently identifies one of the project's classes.

For example:

```text
JMdict explicitly marks:
onomatopoeic or mimetic word

→ semantic classification = mimetic
→ no LLM request
```

Likewise:

```text
JMdict explicitly marks:
idiomatic expression

→ semantic classification = idiom
→ no LLM request
```

However, a generic JMdict marker such as:

```text
expression / phrase / clause
```

does not necessarily distinguish:

```text
construction
idiom
collocation
```

Do NOT automatically map every generic `exp` entry to one of those classes.

If the available JMdict metadata cannot determine the required subtype, use the client LLM fallback.

# 9. JMdict-first semantic decision rule

Implement behavior conceptually equivalent to:

```text
lookup item in JMdict
        ↓
Does JMdict provide an explicit semantic marker
that maps unambiguously to a project class?
        │
   ┌────┴────┐
   │         │
  yes        no
   │         │
   ▼         ▼
use JMdict   use client LLM fallback
```

Fallback is appropriate when:

```text
JMdict entry is absent
```

or:

```text
JMdict entry exists,
but semantic metadata is insufficiently specific
```

# 10. POS and semantic resolution must remain separate

Do not treat:

```text
JMdict entry found
```

as equivalent to:

```text
semantic classification resolved
```

For example:

```text
entry found
POS = verb
generic expression metadata present
```

may result in:

```text
POS:
verb
    ↓
jp-organizer::pos::verb

semantic:
unresolved
    ↓
client LLM fallback
```

The final result might therefore be:

```text
primary_class:
collocation

deck:
Japanese::Vocabulary::Expressions::Collocations

tags:
jp-organizer::kind::expression::collocation
jp-organizer::pos::verb
```

if that is what the existing JMdict POS mapping legitimately returns.

# 11. Semantic definitions for LLM fallback

When JMdict cannot provide a sufficiently specific answer, retain the existing OpenCode/client-LLM classification definitions.

## Mimetic

A Japanese lexical item that imitates or evokes:

* sound;
* movement;
* feeling;
* appearance;
* manner;
* physical state;
* texture;
* psychological state;
* sensory impression.

Examples:

```text
どきどき
ぐっすり
ぺらぺら
すっきり
ぼんやり
さっぱり
あっさり
```

## Construction

A reusable grammatical or phraseological pattern with replaceable material.

Examples:

```text
〜ことになる
〜わけではない
〜に違いない
Xもクソもない
```

## Idiom

A relatively fixed expression whose conventional meaning is substantially figurative or non-compositional.

Examples:

```text
顔が広い
頭が切れる
手を抜く
足を引っ張る
猫の手も借りたい
```

## Collocation

A conventional lexical combination whose overall meaning remains mostly compositional but whose lexical pairing is conventional in Japanese.

Examples:

```text
約束を守る
風邪を引く
興味を持つ
責任を取る
```

# 12. Semantic precedence and primary class

The mutually exclusive `primary_class` is determined only for deck/kind purposes.

Use this conceptual precedence:

```text
specific expression classification
    >
mimetic
    >
word
    >
other
```

Expression values:

```text
construction
idiom
collocation
```

remain mutually exclusive.

If a specific expression classification exists:

```text
primary_class = expression subtype
```

Otherwise, if mimetic:

```text
primary_class = mimetic
```

Otherwise, if it is a normal lexical item:

```text
primary_class = word
```

Otherwise:

```text
primary_class = other
```

This precedence affects only:

```text
deck location
kind tag
```

It does NOT remove or alter independent POS tags.

# 13. Word classification

A vocabulary item becomes:

```text
primary_class = word
```

when it is not classified as:

```text
mimetic
construction
idiom
collocation
```

and it is reasonably recognized as an ordinary lexical item.

Its deck is:

```text
Japanese::Vocabulary::Words
```

and its kind tag is:

```text
jp-organizer::kind::word
```

Its JMdict POS tags are applied exactly as they are for any other vocabulary item.

# 14. Other classification

Use:

```text
Japanese::Vocabulary::Other
```

with:

```text
jp-organizer::kind::other
```

when the item cannot reasonably be assigned to:

```text
word
mimetic
construction
idiom
collocation
```

This does NOT imply that the item must lack POS metadata.

If JMdict provides usable POS metadata, keep the corresponding POS tags independently.

Do not confuse:

```text
jp-organizer::kind::other
```

with:

```text
jp-organizer::pos::other
```

They express unrelated dimensions.

# 15. Semantic source tracking

Store where the semantic classification came from.

Use something conceptually equivalent to:

```text
semantic_source:
    jmdict
    llm
    none
```

A conceptual classification model:

```text
VocabularyClassification

primary_class:
    word
    mimetic
    construction
    idiom
    collocation
    other

jmdict_pos:
    set/list of simplified POS categories

semantic:
    mimetic: bool
    expression_type:
        construction
        idiom
        collocation
        null

semantic_source:
    jmdict
    llm
    none
```

The internal model should make clear that:

```text
jmdict_pos
```

does not depend on:

```text
primary_class
```

# 16. Do not ask the LLM unnecessarily

Only send entries to the client LLM when semantic classification cannot be determined sufficiently from JMdict.

For example, if:

```text
ぐっすり
顔が広い
約束を守る
〜ことになる
```

are being classified, and JMdict directly resolves:

```text
ぐっすり → mimetic
顔が広い → idiom
```

while the other two remain semantically unresolved, return only:

```text
約束を守る
〜ことになる
```

to the client LLM.

POS classification still runs through JMdict for all four entries.

# 17. Semantic cache

Update the semantic cache to store the classification source.

Store enough information such as:

```text
stable note identity
entry hash
mimetic
expression_type
semantic_source
semantic_mapping_schema_version
```

Reuse compatible cached classifications for unchanged entries.

If an existing LLM-derived result is present but the updated JMdict semantic mapper now provides a clear direct classification, prefer the explicit JMdict result.

Conceptually:

```text
cached LLM semantic result
       +
new decisive JMdict semantic result
       ↓
JMdict result wins
```

Do not re-run the LLM unnecessarily.

# 18. JMdict SQLite changes

Inspect the existing compact JMdict index.

If it currently indexes only POS data, extend it with only the semantic metadata needed by this project.

Do NOT turn it into a complete copy of JMdict.

Store only data needed for:

```text
form lookup
POS classification
semantic classification
```

A possible addition is:

```text
semantic_metadata
-----------------
entry_id
semantic_code
```

or an equivalent normalized representation.

Continue using SQLite for normal classification.

Do not parse the original XML during normal synchronization.

If the index schema changes:

* bump the schema version;
* rebuild safely;
* update `jp_index_status`;
* update tests;
* update documentation.

# 19. Central JMdict semantic mapper

Create or update a central mapper conceptually like:

```text
jmdict_semantic_mapper
```

It must convert raw JMdict semantic metadata into one of:

```text
decisive mimetic
decisive idiom
decisive construction
decisive collocation
insufficient semantic information
no semantic classification
```

Only create direct Construction or Collocation mappings if the actual JMdict metadata genuinely supports those distinctions.

Do not invent such mappings merely to avoid LLM fallback.

For example:

```text
on-mim
→ decisive mimetic
```

```text
id
→ decisive idiom
```

while:

```text
exp
→ expression-like
→ subtype unresolved
→ LLM fallback
```

if that reflects the actual dictionary semantics.

# 20. New kind tags vs old semantic tags

The new kind tags are:

```text
jp-organizer::kind::word
jp-organizer::kind::mimetic
jp-organizer::kind::expression::construction
jp-organizer::kind::expression::idiom
jp-organizer::kind::expression::collocation
jp-organizer::kind::other
```

The following old classification tags become obsolete:

```text
jp-organizer::kind::vocabulary
jp-organizer::mimetic
jp-organizer::expression::construction
jp-organizer::expression::idiom
jp-organizer::expression::collocation
```

Remove these old managed semantic/kind tags during reconciliation.

POS tags remain valid and independent:

```text
jp-organizer::pos::*
```

Do NOT remove a POS tag merely because an entry is a Mimetic or Expression.

# 21. Migration from existing state

Existing notes may currently use:

```text
jp-organizer::kind::vocabulary
jp-organizer::mimetic
jp-organizer::expression::construction
jp-organizer::expression::idiom
jp-organizer::expression::collocation
jp-organizer::pos::*
```

On migration:

1. retain/recalculate JMdict POS classification;
2. inspect JMdict semantic metadata;
3. use decisive JMdict semantic classification when available;
4. otherwise reuse compatible cached LLM semantic classification;
5. otherwise request client LLM fallback;
6. determine exactly one `primary_class`;
7. move the existing card to the correct leaf deck;
8. remove obsolete old kind/semantic tags;
9. apply exactly one new kind tag;
10. apply all appropriate JMdict POS tags independently;
11. preserve source identity;
12. preserve managed-note identity;
13. preserve source mapping;
14. preserve unrelated user tags.

Do not duplicate notes during migration.

# 22. Synchronization desired state

Update reconciliation so each vocabulary item's desired state includes at least:

```text
primary_class
target_deck
kind_tag
pos_tags
semantic_source
```

For example:

```json
{
  "entry": "ぐっすり",
  "primary_class": "mimetic",
  "target_deck": "Japanese::Vocabulary::Mimetics",
  "kind_tag": "jp-organizer::kind::mimetic",
  "pos_tags": [
    "jp-organizer::pos::adverb"
  ],
  "semantic_source": "jmdict"
}
```

The deck/kind classification and POS metadata must be reconciled independently.

# 23. Classification changes move existing cards

If an entry changes from:

```text
primary_class = word
```

to:

```text
primary_class = mimetic
```

move the existing card:

```text
Japanese::Vocabulary::Words
→ Japanese::Vocabulary::Mimetics
```

and replace:

```text
jp-organizer::kind::word
```

with:

```text
jp-organizer::kind::mimetic
```

but retain/recalculate its JMdict POS tags independently.

Do not create a second note.

# 24. Stale tag cleanup

When reconciling managed notes:

For kind tags:

```text
remove all stale jp-organizer::kind::* vocabulary tags
apply exactly one current vocabulary kind tag
```

For POS tags:

```text
remove stale jp-organizer::pos::* tags
recalculate from current JMdict POS data
apply current POS tags
```

These are two separate reconciliation operations.

Do not condition POS cleanup/application on `primary_class`.

Preserve all unrelated user-created tags.

# 25. Semantic classification handshake

Update `jp_sync` and `jp_classify_vocabulary`.

Required flow:

```text
source entries
      ↓
JMdict lookup
      ├── calculate POS
      └── inspect semantic metadata
              ↓
resolve semantic classes JMdict can determine
              ↓
collect only unresolved semantic entries
              ↓
semantic_classification_required
              ↓
OpenCode classifies unresolved entries
              ↓
submit fallback results
              ↓
determine primary_class
              ↓
complete reconciliation
```

Do not send JMdict-resolved semantic entries to the LLM.

# 26. Vocabulary lookup output

Update `jp_lookup_vocabulary` so debugging clearly separates:

```text
kind/deck classification
POS classification
semantic source
```

Example:

```json
{
  "entry": "ぐっすり",
  "primary_class": "mimetic",
  "target_deck": "Japanese::Vocabulary::Mimetics",
  "kind_tag": "jp-organizer::kind::mimetic",
  "jmdict": {
    "found": true,
    "pos_tags": [
      "jp-organizer::pos::adverb"
    ],
    "semantic_markers": [
      "on-mim"
    ]
  },
  "semantic": {
    "mimetic": true,
    "expression_type": null,
    "source": "jmdict"
  }
}
```

An LLM fallback example:

```json
{
  "entry": "約束を守る",
  "primary_class": "collocation",
  "target_deck": "Japanese::Vocabulary::Expressions::Collocations",
  "kind_tag": "jp-organizer::kind::expression::collocation",
  "jmdict": {
    "pos_tags": [
      "jp-organizer::pos::verb"
    ]
  },
  "semantic": {
    "mimetic": false,
    "expression_type": "collocation",
    "source": "llm"
  }
}
```

Exact fields may differ, but the separation must be clear.

# 27. Kanji behavior

Keep:

```text
Japanese::Kanji
```

with:

```text
jp-organizer::kind::kanji
```

unchanged.

Kanji extraction must consider vocabulary entries in ALL vocabulary leaf decks:

```text
Japanese::Vocabulary::Words
Japanese::Vocabulary::Mimetics
Japanese::Vocabulary::Expressions::Constructions
Japanese::Vocabulary::Expressions::Idioms
Japanese::Vocabulary::Expressions::Collocations
Japanese::Vocabulary::Other
```

Do not restrict kanji extraction by kind or POS.

# 28. Tests — kind/POS independence

Add explicit tests for independence between primary class and POS.

For example:

```text
JMdict:
ぐっすり
→ adverb
→ mimetic marker
```

Expected:

```text
primary_class:
mimetic

deck:
Japanese::Vocabulary::Mimetics

tags:
jp-organizer::kind::mimetic
jp-organizer::pos::adverb
```

Another example:

```text
JMdict:
normal lexical adverb
→ adverb
→ no semantic class
```

Expected:

```text
primary_class:
word

deck:
Japanese::Vocabulary::Words

tags:
jp-organizer::kind::word
jp-organizer::pos::adverb
```

The difference is the kind/deck classification only.

POS remains independently present in both cases.

# 29. Tests — JMdict-first semantic classification

Add fixture cases for:

1. explicit JMdict mimetic marker;
2. explicit JMdict idiom marker;
3. generic expression marker;
4. normal lexical item;
5. entry without sufficient semantic metadata;
6. entry absent from JMdict.

Verify:

```text
explicit mimetic
→ JMdict semantic result
→ no LLM request
```

```text
explicit idiom
→ JMdict semantic result
→ no LLM request
```

```text
generic expression
→ insufficient subtype
→ LLM fallback
```

```text
JMdict absent/insufficient
→ LLM fallback
```

POS tests must remain independent.

# 30. Tests — deck mutual exclusivity

Verify:

1. every managed vocabulary note belongs to exactly one vocabulary leaf deck;
2. every managed vocabulary note has exactly one vocabulary kind tag;
3. no duplicate notes are created for overlapping POS/semantic classifications;
4. a Mimetic may also have POS tags;
5. an Idiom may also have POS tags;
6. a Collocation may also have POS tags;
7. a Construction may also have POS tags when JMdict lookup supplies them;
8. Other items may retain POS metadata if JMdict supplies it;
9. changing `primary_class` moves the card instead of duplicating it;
10. POS changes do not move cards unless semantic/primary classification also changes.

# 31. Update README.md

Update `README.md` comprehensively.

It must prominently show:

```text
Japanese
├── Vocabulary
│   ├── Words
│   ├── Mimetics
│   ├── Expressions
│   │   ├── Constructions
│   │   ├── Idioms
│   │   └── Collocations
│   └── Other
└── Kanji
```

Explicitly explain:

> Vocabulary deck placement is mutually exclusive. Every managed vocabulary note has exactly one primary kind and lives in exactly one vocabulary leaf deck.

Also explicitly explain:

> POS tags are independent of the vocabulary kind/deck classification. POS is derived from JMdict for all vocabulary items.

Show:

```text
Kind/deck:
mutually exclusive

POS:
independent metadata
```

Include the example:

```text
ぐっすり

deck:
Vocabulary::Mimetics

tags:
jp-organizer::kind::mimetic
jp-organizer::pos::adverb
```

Document semantic resolution as:

```text
JMdict semantic metadata
        ↓
sufficiently specific?
   ├── yes → use JMdict
   └── no  → client LLM fallback
```

Remove any README text claiming:

* semantic classification is always LLM-driven;
* POS tags apply only to Words;
* non-Word classes should have their POS tags removed.

# 32. Update TASK.md

Update `TASK.md` comprehensively so it becomes the authoritative specification for the new behavior.

Do not append only a correction.

Rewrite affected sections covering:

* permanent deck hierarchy;
* kind tags;
* POS tags;
* classification architecture;
* JMdict semantic classification;
* LLM fallback;
* responsibility boundaries;
* semantic cache;
* reconciliation;
* migration;
* MCP workflow;
* lookup output;
* tests;
* README requirements;
* completion criteria.

The revised `TASK.md` must clearly contain these independent invariants:

```text
PRIMARY KIND:

exactly one primary_class
        ↓
exactly one vocabulary leaf deck
        ↓
exactly one vocabulary kind tag
```

and:

```text
POS:

JMdict-derived
independent of primary_class
may coexist with any vocabulary kind
```

Remove all statements saying:

```text
POS tags only when primary_class == word
```

or equivalent.

# 33. Preserve existing functionality

Do not regress:

* JMdict indexing;
* KANJIDIC indexing;
* AnkiConnect;
* missing-index handling;
* dictionary-path persistence/discovery;
* source-note identity;
* ownership protection;
* reconciliation;
* additions;
* edits;
* removals;
* kanji generation;
* kanji deduplication;
* semantic cache;
* LLM semantic fallback;
* dry-run;
* idempotency;
* structured errors.

# 34. Implementation sequence

Perform the modification rather than only describing it.

1. Inspect the current repository.
2. Inspect tests.
3. Inspect current JMdict schema/mappings.
4. Inspect `README.md`.
5. Inspect `TASK.md`.
6. Extend JMdict indexing with required semantic metadata if necessary.
7. Implement centralized JMdict semantic mapping.
8. Make semantic classification JMdict-first.
9. Keep client LLM as fallback.
10. Introduce/update `primary_class`.
11. Add mutually exclusive leaf-deck routing.
12. Replace old semantic/kind tags with new kind tags.
13. Keep POS reconciliation independent of kind.
14. Update semantic cache/source tracking.
15. Implement safe migration.
16. Update card movement logic.
17. Ensure Kanji extraction uses every vocabulary leaf deck.
18. Update MCP result models.
19. Update tests.
20. Run full tests.
21. Fix regressions.
22. Run lint/type checks.
23. Update README.md.
24. Update TASK.md.
25. Search the repository for obsolete assumptions.
26. Provide a concise final implementation report.

# 35. Final verification

Before declaring completion, explicitly verify:

```text
✓ exactly one primary vocabulary class per managed vocabulary item
✓ exactly one vocabulary leaf deck per managed vocabulary item
✓ exactly one vocabulary kind tag per managed vocabulary item

✓ POS classification still uses JMdict
✓ POS tags are independent of kind/deck classification
✓ POS tags may coexist with Words, Mimetics, Expressions, and Other
✓ the LLM never determines POS

✓ semantic classification checks JMdict first
✓ explicit JMdict mimetic markers avoid LLM calls
✓ explicit JMdict idiom markers avoid LLM calls
✓ insufficient JMdict semantic information falls back to the client LLM
✓ generic expression metadata is not overinterpreted

✓ classification changes move cards rather than duplicating notes
✓ POS changes alone do not duplicate or move notes
✓ old semantic/kind tags are migrated away
✓ existing compatible semantic cache is reused
✓ kanji extraction covers all vocabulary subdecks
✓ unmanaged notes and tags remain safe
✓ repeated sync is idempotent
✓ dry-run performs no mutations

✓ README.md describes the implemented behavior
✓ TASK.md describes the implemented behavior
✓ all tests pass
```

In the final implementation report include:

* files changed;
* JMdict semantic mappings implemented;
* which semantic classes JMdict resolves directly;
* which classes still use LLM fallback;
* migration behavior;
* test results;
* lint/type-check results;
* remaining compatibility limitations.
