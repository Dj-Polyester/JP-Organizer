# jp-organizer — Japanese Anki Organizer MCP Server

Build a production-quality MCP server named **`jp-organizer`** for organizing Japanese-learning flashcards in Anki.

The server will be used from an MCP-capable LLM client such as **OpenCode**.

The user should be able to provide the name of an Anki deck containing Japanese entries and say things such as:

```text
Organize my Japanese Inbox deck.
```

or:

```text
Update my Japanese decks.
```

OpenCode should use the MCP server to:

1. synchronize vocabulary;
2. classify vocabulary POS using JMdict;
3. classify expressions and mimetics using the OpenCode LLM;
4. extract kanji;
5. obtain kanji meanings/readings from KANJIDIC;
6. create/update/remove the appropriate Anki notes;
7. propagate later source-deck additions, edits, and removals.

Use **Python** unless the repository strongly favors another language.

Use the current official MCP SDK and support **stdio transport**.

Use **AnkiConnect** for all interaction with Anki.

Do not manipulate Anki's collection SQLite database directly.

---

# 1. Permanent Anki structure

The permanent managed structure is:

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

The corresponding Anki deck names are:

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

`Japanese::Kanji` contains unique kanji extracted from the current vocabulary entries across all vocabulary leaf decks.

---

# 2. Required tags

Every managed vocabulary note receives exactly one kind tag:

```text
jp-organizer::kind::word
jp-organizer::kind::mimetic
jp-organizer::kind::expression::construction
jp-organizer::kind::expression::idiom
jp-organizer::kind::expression::collocation
jp-organizer::kind::other
```

Every managed kanji note receives:

```text
jp-organizer::kind::kanji
```

## POS tags

POS classifications are determined from **JMdict**, not by the LLM.

```text
jp-organizer::pos::noun
jp-organizer::pos::verb
jp-organizer::pos::adjective
jp-organizer::pos::adverb
jp-organizer::pos::other
```

POS tags are **independent** of the vocabulary kind/deck classification. POS is derived from JMdict for **all** vocabulary items, regardless of their primary class.

## Two independent dimensions

```text
Kind/deck:       mutually exclusive
POS:             independent metadata
```

For example:

```text
ぐっすり
```

may have:

```text
jp-organizer::kind::mimetic
jp-organizer::pos::adverb
```

JMdict supplies both the `adverb` POS classification and the `mimetic` semantic marker (`on-mim`).

The LLM is used only when JMdict cannot provide a sufficiently specific semantic classification.

---

# 3. Classification architecture

Classification is intentionally hybrid and JMdict-first.

```text
                    Vocabulary entry
                          │
                          ▼
                    JMdict SQLite
                          │
            ┌─────────────┼──────────────┐
            │             │              │
            ▼             ▼              ▼
       POS classification    semantic metadata
            │                    │
            │         ┌─────────┴──────────┐
            │         │                    │
            │    decisive?            insufficient?
            │    (on-mim, id)         (exp, absent)
            │         │                    │
            │         ▼                    ▼
            │    use JMdict           OpenCode LLM
            │         │                    │
            │         └────────┬───────────┘
            │                  ▼
            │           primary_class
            │                  │
            │                  ▼
            │         one vocabulary leaf deck
            │                  │
            │                  ▼
            │           one kind tag
            │
            └────────────┬───────────────┘
                         ▼
                  final Anki tags
```

Do not let the LLM override JMdict POS information.

JMdict is the **first** source for semantic classification. Only when JMdict cannot determine the required subtype does the system fall back to the OpenCode LLM.

---

# 4. What is a mimetic?

For this project, a **mimetic** is a Japanese lexical item that imitates or evokes:

* a sound;
* movement;
* physical manner;
* feeling;
* appearance;
* state;
* texture;
* psychological condition;
* sensory impression.

Japanese uses this category much more extensively than English.

Examples include:

```text
どきどき
```

heart pounding / nervous excitement

```text
ぐっすり
```

sleeping soundly

```text
ぺらぺら
```

fluently, or thin/flapping depending on context

```text
すっきり
```

refreshed, clear, uncluttered

```text
ぼんやり
```

vaguely, absent-mindedly, dimly

```text
さっぱり
```

refreshed/clean, completely, or not at all depending on context

```text
あっさり
```

lightly, simply, without fuss, or light in taste

Mimetics include categories often described linguistically as:

* 擬音語;
* 擬声語;
* 擬態語;
* 擬情語;
* related sound-symbolic vocabulary.

Do NOT implement the classifier simply as:

```text
repeated kana => mimetic
```

because:

* not every mimetic has obvious reduplication;
* not every reduplicated form is necessarily being used mimetically.

The LLM should classify based on the lexical meaning/function of the complete entry.

A mimetic may simultaneously have an ordinary POS classification.

For example:

```text
ぐっすり
```

may be both:

```text
jp-organizer::pos::adverb
jp-organizer::mimetic
```

These tags are not mutually exclusive.

---

# 5. What is an expression?

An **expression** in this project is a multi-word unit, grammatical pattern, or conventional phrase that is useful to learn as a unit rather than simply as isolated component words.

There are exactly three expression categories:

```text
construction
idiom
collocation
```

Not every multi-word Japanese sequence is an expression.

For example, a complete ordinary sentence should not automatically receive an expression tag simply because it contains several words.

The LLM must distinguish reusable/conventional lexical units from arbitrary compositions.

---

# 6. Construction

A **construction** is a reusable grammatical or phraseological pattern containing one or more slots where different material can appear.

Examples:

```text
〜ことになる
〜わけではない
〜に違いない
Xもクソもない
```

For example:

```text
日本へ行くことになった。
```

contains the reusable construction:

```text
〜ことになる
```

while:

```text
日本へ行く
```

fills one of its slots.

Construction indicators include:

* productive or semi-productive grammatical patterns;
* an explicit `〜` or `X` slot;
* a portion of the expression can systematically be replaced;
* learners benefit from learning the pattern itself.

Apply:

```text
jp-organizer::expression::construction
```

Examples:

```text
〜ことになる
〜わけではない
〜に違いない
Xもクソもない
```

Do not classify an ordinary fixed phrase as a construction merely because some words could theoretically be replaced.

There should be a recognizable reusable pattern.

---

# 7. Idiom

An **idiom** is a relatively fixed expression whose conventional overall meaning is not straightforwardly predictable from the literal meanings of its component words.

Example:

```text
顔が広い
```

Literally:

```text
one's face is wide
```

but idiomatically it means approximately:

```text
to be well-connected
```

Other examples:

```text
頭が切れる
手を抜く
足を引っ張る
猫の手も借りたい
```

Apply:

```text
jp-organizer::expression::idiom
```

The primary distinction between an idiom and collocation is semantic compositionality.

If the conventional meaning is significantly figurative or cannot readily be predicted from the individual words, prefer `idiom`.

---

# 8. Collocation

A **collocation** is a conventional combination of words whose overall meaning remains mostly compositional/literal, but Japanese strongly prefers that particular lexical combination.

Examples:

```text
約束を守る
```

keep a promise

```text
風邪を引く
```

catch a cold

```text
興味を持つ
```

have/take an interest

```text
責任を取る
```

take responsibility

Apply:

```text
jp-organizer::expression::collocation
```

The distinction from an idiom is:

```text
collocation:
meaning mostly follows from components,
but the lexical pairing is conventional

idiom:
overall meaning is substantially lexicalized,
figurative, or non-compositional
```

---

# 9. Expression decision hierarchy

When the LLM evaluates an entry, use the following conceptual decision process.

First ask:

```text
Is this actually a conventional/reusable expression
rather than an ordinary lexical word or arbitrary sentence?
```

If no:

```text
no expression tag
```

If yes, ask:

```text
Does it primarily behave as a reusable pattern
with replaceable grammatical/lexical slots?
```

If yes:

```text
construction
```

Otherwise ask:

```text
Is its conventional meaning significantly
non-literal/non-compositional?
```

If yes:

```text
idiom
```

Otherwise ask:

```text
Is it a conventional lexical combination whose
meaning is mostly compositional?
```

If yes:

```text
collocation
```

Otherwise:

```text
no expression tag
```

Normally assign **at most one** of:

```text
construction
idiom
collocation
```

to an individual vocabulary entry.

Do not stack several expression categories simply because classification is uncertain.

`mimetic`, however, is independent and may coexist with any other applicable tag.

---

# 10. Conservative LLM classification

Semantic classification should be conservative.

The LLM should not force every entry into one of the semantic categories.

Valid semantic output may be:

```json
{
  "mimetic": false,
  "expression_type": null
}
```

Use an expression or mimetic tag only when the classification is reasonably supported by the entry.

If classification is genuinely uncertain, prefer no semantic tag rather than inventing one.

The LLM should consider the complete vocabulary entry.

Do not classify individual characters or substrings independently.

---

# 11. Responsibility boundaries

The responsibilities are:

## MCP server

Responsible for:

* Anki access;
* JMdict indexing;
* KANJIDIC indexing;
* SQLite lookup;
* JMdict POS mapping;
* kanji extraction;
* synchronization;
* persistence;
* applying semantic classifications supplied by the client;
* maintaining tags;
* ownership-safe deletion/reconciliation.

## OpenCode LLM

Responsible for:

* understanding user requests;
* locating XML dictionary files when necessary;
* invoking MCP tools;
* semantic classification of:

  * mimetics;
  * constructions;
  * idioms;
  * collocations;
* submitting those semantic classifications back to the MCP server.

The MCP server should NOT need its own external LLM provider/API key.

Use the already-running OpenCode model for semantic reasoning.

---

# 12. Why semantic classification is client-side

Do not assume an MCP server can synchronously invoke the model operating the MCP client.

Therefore design the protocol so the MCP server can explicitly request semantic decisions from OpenCode.

The server should identify entries requiring semantic classification and return them to the client.

OpenCode then evaluates those entries and supplies the classification in the next tool call.

This makes the server independent of:

* OpenAI;
* Anthropic;
* Gemini;
* local LLM providers;
* API keys;
* model-specific SDKs.

---

# 13. Semantic classification request format

When an entry requires LLM classification, the MCP server should return something conceptually like:

```json
{
  "semantic_classification_required": [
    {
      "id": "source-note-123",
      "entry": "顔が広い"
    },
    {
      "id": "source-note-124",
      "entry": "ぐっすり"
    }
  ]
}
```

The ID must be a stable identifier allowing the result to be associated with the correct vocabulary note.

OpenCode should classify each entry.

Example response data passed back to the MCP server:

```json
[
  {
    "id": "source-note-123",
    "mimetic": false,
    "expression_type": "idiom"
  },
  {
    "id": "source-note-124",
    "mimetic": true,
    "expression_type": null
  }
]
```

Allowed `expression_type` values are exactly:

```text
construction
idiom
collocation
null
```

Do not allow arbitrary tag strings from the LLM.

The server must validate all supplied semantic classifications before applying them.

---

# 14. Semantic classification caching

Do not ask the LLM to reclassify every unchanged vocabulary entry during every sync.

Persist semantic classification state.

Store at least:

```text
stable source/managed note identity
normalized entry text or hash
mimetic boolean
expression type
semantic classifier schema/version
```

When an entry is unchanged and already has a semantic classification under the current classification schema, reuse it.

Example:

```text
First synchronization:

顔が広い
   ↓
OpenCode classifies
   ↓
idiom
   ↓
store result
```

Later synchronization with unchanged entry:

```text
顔が広い
   ↓
stored classification found
   ↓
reuse idiom
```

No additional LLM classification is required.

If the entry changes:

```text
顔が広い
    ↓
顔が大きい
```

invalidate the stored semantic result and ask OpenCode to classify the new text.

Also support an explicit option to force semantic reclassification.

For example:

```json
{
  "force_semantic_reclassification": true
}
```

---

# 15. JMdict POS classification

JMdict is authoritative for POS.

Index only the information needed for POS lookup.

At minimum store:

* JMdict sequence/entry ID;
* written forms (`keb`);
* reading forms (`reb`);
* POS metadata needed for this taxonomy.

Convert JMdict POS data into:

```text
noun
verb
adjective
adverb
other
```

and then into:

```text
jp-organizer::pos::noun
jp-organizer::pos::verb
jp-organizer::pos::adjective
jp-organizer::pos::adverb
jp-organizer::pos::other
```

A vocabulary item can receive multiple POS tags where justified by JMdict.

For example, if JMdict shows legitimate noun and verb uses, both may be attached.

Use:

```text
jp-organizer::pos::other
```

only when none of:

```text
noun
verb
adjective
adverb
```

apply.

---

# 16. JMdict classification mapping

Create a centralized mapping module containing the mapping from JMdict POS entities/codes into the simplified jp-organizer taxonomy.

Do not spread mapping logic throughout the codebase.

Conceptually:

```text
JMdict POS
    │
    ▼
central mapping
    │
    ├── noun
    ├── verb
    ├── adjective
    ├── adverb
    └── other
```

Inspect the actual JMdict entity definitions supplied by the dictionary.

Do not rely on brittle matching against display strings if canonical entity codes are available.

Document the mapping in README.

Unit-test it.

---

# 17. JMdict SQLite index

Do NOT store the full JMdict dictionary.

A reasonable schema is:

```text
entries
-------
entry_id

forms
-----
entry_id
form
form_type

pos
---
entry_id
pos_category
```

Add an index on:

```text
forms.form
```

The exact normalized schema may differ if appropriate.

Do not index:

* English glosses;
* examples;
* frequency information;
* unrelated cross-references;
* unrelated metadata;

unless genuinely required for POS lookup.

Use streaming XML parsing.

Do not load the complete XML tree into memory.

---

# 18. KANJIDIC indexing

KANJIDIC supplies information for the Kanji deck.

Index only:

* kanji literal;
* meanings;
* readings.

Preserve at least:

```text
on
kun
nanori
```

reading categories.

Prefer English meanings where KANJIDIC distinguishes languages.

Do not unnecessarily index:

* stroke count;
* grade;
* frequency;
* radical data;
* dictionary references;
* SKIP codes;
* unrelated metadata.

Use streaming XML parsing.

---

# 19. Suggested KANJIDIC SQLite schema

For example:

```text
kanji
-----
literal

meanings
--------
literal
meaning
language
ordinal

readings
--------
literal
reading
reading_type
ordinal
```

Index:

```text
literal
```

Deduplicate meanings and readings while preserving stable source order where practical.

---

# 20. Dictionary indexing lifecycle

Dictionary XML files are indexing sources only.

Normal operations must use SQLite.

Before an operation requiring dictionary information:

```text
Does the required SQLite index exist and have
a compatible schema?
```

If yes:

```text
use SQLite
```

If no:

```text
return a structured missing-index response
```

The MCP server itself must NOT recursively search the user's filesystem.

Filesystem discovery belongs to OpenCode.

---

# 21. OpenCode recovery from missing indexes

When the MCP server reports a missing JMdict or KANJIDIC index, OpenCode should automatically attempt to locate the corresponding XML.

Possible JMdict filenames include:

```text
JMdict
JMdict.xml
JMdict_e
JMdict_e.xml
JMdict*.xml
```

Possible KANJIDIC filenames include:

```text
kanjidic2.xml
kanjidic*.xml
KANJIDIC*.xml
```

Do not trust filenames alone.

Inspect candidate files enough to verify their format/root structure.

If exactly one appropriate dictionary is found:

```text
find XML
   ↓
jp_index_dictionaries
   ↓
retry original operation
```

If multiple plausible files exist and the correct one cannot safely be determined, show the choices to the user.

If none can be found, ask the user for the path.

---

# 22. Indexing invariant

Do not describe indexing as literally "only the first time."

The rule is:

> Build or rebuild a dictionary index whenever the required SQLite index is missing, invalid, incompatible, stale according to the chosen validation policy, or explicitly requested to be rebuilt.

Examples:

```text
first use:
XML → SQLite → sync

later use:
SQLite → sync

index deleted:
XML → SQLite → sync

schema incompatible:
XML → rebuild SQLite → sync

only JMdict missing:
rebuild JMdict only

both valid:
do not parse XML
```

Normal lookup must NEVER fall back to scanning XML.

---

# 23. Index metadata

Store metadata sufficient to determine:

* schema version;
* creation time;
* source path;
* source modification time;
* file size;
* optionally source hash;
* dictionary version where discoverable.

Do not unnecessarily calculate expensive full-file hashes on every normal sync.

---

# 24. Source deck modes

Support two modes.

## Mode A — `Japanese::Vocabulary` is the source

If:

```text
source_deck_name = Japanese::Vocabulary
```

classify those notes in place.

Do not create duplicates.

## Mode B — another deck is the source

Example:

```text
Japanese Inbox
```

Treat that deck as source-of-truth and mirror its entries into:

```text
Japanese::Vocabulary
```

Maintain stable source-to-target identity.

Only manage notes owned by jp-organizer.

Never delete unrelated user-created notes from `Japanese::Vocabulary`.

---

# 25. Vocabulary note type

For mirrored notes, create a dedicated note model:

```text
JP Organizer Vocabulary
```

with at least:

```text
Entry
SourceDeck
SourceNoteId
```

Internal metadata fields may be added if necessary.

The visible flashcard only needs to expose `Entry` unless additional fields are intentionally useful.

---

# 26. Determining the Japanese entry

The source deck may contain arbitrary note types.

The tool accepts optional:

```text
entry_field
```

Selection rules:

1. if `entry_field` was supplied, use it;
2. otherwise examine fields deterministically;
3. select an appropriate non-empty field containing Japanese;
4. if several fields are genuinely ambiguous, report the note rather than guessing.

Anki fields may contain HTML.

For linguistic processing:

* strip HTML;
* decode entities;
* normalize surrounding whitespace.

Do not modify the original source note.

Example:

```html
<b>食べる</b>
```

should be processed as:

```text
食べる
```

Do not perform aggressive normalization that changes lexical identity.

---

# 27. Complete vocabulary classification

For each vocabulary entry, final tags should be assembled as:

```text
kind tag (exactly one)
+
JMdict POS tags
```

Example:

```text
ぐっすり
```

could become:

```text
jp-organizer::kind::mimetic
jp-organizer::pos::adverb
```

Example:

```text
顔が広い
```

might become:

```text
jp-organizer::kind::expression::idiom
jp-organizer::pos::other
```

depending on the JMdict POS lookup.

Example:

```text
約束を守る
```

might receive:

```text
jp-organizer::kind::expression::collocation
jp-organizer::pos::other
```

plus whatever POS information JMdict actually supports for the indexed entry.

Do not invent POS tags merely because the LLM thinks they are linguistically reasonable.

## primary_class

Every managed vocabulary entry has exactly one `primary_class`:

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
word         → Japanese::Vocabulary::Words
mimetic      → Japanese::Vocabulary::Mimetics
construction → Japanese::Vocabulary::Expressions::Constructions
idiom        → Japanese::Vocabulary::Expressions::Idioms
collocation  → Japanese::Vocabulary::Expressions::Collocations
other        → Japanese::Vocabulary::Other
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

---

# 28. Unmatched JMdict entries

A vocabulary entry may not match JMdict because it is:

* a construction;
* a phrase;
* an inflected expression;
* a sentence fragment;
* absent from the dictionary.

Do not treat this as fatal.

If no JMdict POS match exists, assign:

```text
jp-organizer::pos::other
```

and report it as an unmatched JMdict entry.

It may still receive an LLM semantic classification.

For example:

```text
〜わけではない
```

might have:

```text
jp-organizer::kind::vocabulary
jp-organizer::pos::other
jp-organizer::expression::construction
```

---

# 29. Kanji extraction

After determining the CURRENT Vocabulary state, derive the desired unique Kanji set.

Do not rely solely on broad Unicode ranges.

Preferred approach:

1. inspect characters appearing in vocabulary entries;
2. batch-query the KANJIDIC SQLite index;
3. if KANJIDIC contains the character, treat it as a kanji entry.

This naturally excludes most:

* kana;
* punctuation;
* Latin characters;
* unrelated symbols.

---

# 30. Kanji note type

Create:

```text
JP Organizer Kanji
```

with fields:

```text
Entry
Meanings
Readings
```

Each managed Kanji note receives:

```text
jp-organizer::kind::kanji
```

Example:

```text
Entry:
食

Meanings:
eat; food

Readings:
On: ショク
Kun: た.べる, く.う
Nanori: ...
```

---

# 31. Kanji deduplication

If Vocabulary contains:

```text
食べる
食事
食堂
```

create only one:

```text
食
```

Kanji note.

Kanji uniqueness is by literal character.

---

# 32. Reconciliation

Synchronization must use reconciliation rather than fragile event tracking.

Conceptually:

```text
current source state
       +
JMdict index
       +
stored semantic classifications
       +
new semantic classifications from OpenCode
       +
KANJIDIC index
       ↓
desired managed state
       ↓
compare against actual managed state
       ↓
create / update / delete
```

This is essential for reliable removal handling.

---

# 33. Addition propagation

If a new entry appears in the source deck:

```text
約束を守る
```

the next synchronization should:

1. create/update its Vocabulary mirror;
2. obtain POS classification from JMdict;
3. request semantic classification from OpenCode;
4. apply:

   * collocation if appropriate;
5. extract any newly required Kanji;
6. create missing Kanji cards.

---

# 34. Modification propagation

Suppose:

```text
学生
```

changes to:

```text
先生
```

The next synchronization must:

1. detect that source content changed;
2. update the Vocabulary mirror;
3. rerun JMdict POS lookup;
4. invalidate the old semantic classification;
5. request a new semantic classification from OpenCode;
6. recalculate the desired Kanji set;
7. add/remove Kanji cards as required.

---

# 35. Removal propagation

Suppose the vocabulary is:

```text
日本
学生
食べる
```

with kanji:

```text
日
本
学
生
食
```

If:

```text
食べる
```

is removed, and no remaining vocabulary entry contains:

```text
食
```

remove the managed `食` Kanji note.

If another remaining entry contains `食`, keep it.

Likewise, when a source entry disappears, remove its jp-organizer-managed Vocabulary mirror.

Never delete:

* source notes;
* unmanaged Vocabulary notes;
* unmanaged Kanji notes;
* arbitrary user-created data.

---

# 36. Ownership

Deck membership alone is NOT sufficient proof of ownership.

Use:

* dedicated note types;
* persistent mappings;
* internal metadata;

or a combination.

Only notes positively identified as managed by jp-organizer may be deleted automatically.

---

# 37. Organizer state

Use a SQLite state database such as:

```text
organizer-state.sqlite
```

Store relationships such as:

```text
source note ID
    ↕
managed Vocabulary note ID
```

and semantic classification cache.

A conceptual semantic table may contain:

```text
note_key
entry_hash
mimetic
expression_type
classifier_schema_version
```

Do not store unnecessary model chain-of-thought or long LLM explanations.

---

# 38. Stale tag handling

When updating classification, remove stale jp-organizer classification tags in these namespaces:

```text
jp-organizer::pos::*
jp-organizer::kind::*
jp-organizer::mimetic
jp-organizer::expression::*
```

and reconstruct them from current classification state.

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

Preserve:

* unrelated user tags;
* tags from other tools;
* tags outside jp-organizer's managed namespaces.

---

# 39. MCP workflow

The workflow must support the fact that semantic classification requires the OpenCode model.

A clean user experience should look like:

```text
User:
"Organize Japanese Inbox"

OpenCode
   ↓
jp_sync(...)
   ↓
server performs source analysis + JMdict work
   ↓
server returns entries needing semantic classification
   ↓
OpenCode classifies those entries
   ↓
jp_sync(... semantic_classifications=...)
   ↓
server validates classifications
   ↓
server performs complete reconciliation
   ↓
done
```

This should happen automatically without requiring the user to manually classify individual entries.

---

# 40. `jp_sync`

This is the primary day-to-day tool.

Inputs approximately:

```json
{
  "source_deck_name": "Japanese Inbox",
  "entry_field": null,
  "dry_run": false,
  "force_semantic_reclassification": false,
  "semantic_classifications": null
}
```

The system first attempts semantic classification from JMdict:

- **Explicit mimetic marker** (`on-mim`) → classified as mimetic, no LLM call
- **Explicit idiom marker** (`id`) → classified as idiom, no LLM call
- **Generic expression marker** (`exp`) → expression-like but subtype unresolved → **LLM fallback**
- **Normal lexical item** → word, no LLM call
- **Absent from JMdict** → **LLM fallback**

Only entries that JMdict cannot resolve sufficiently are returned for LLM classification:

```json
{
  "status": "semantic_classification_required",
  "requests": [
    {
      "id": "123",
      "entry": "顔が広い"
    },
    {
      "id": "124",
      "entry": "約束を守る"
    }
  ]
}
```

OpenCode should classify them using the definitions in this specification and call `jp_sync` again with:

```json
{
  "source_deck_name": "Japanese Inbox",
  "semantic_classifications": [
    {
      "id": "123",
      "mimetic": false,
      "expression_type": "idiom"
    },
    {
      "id": "124",
      "mimetic": false,
      "expression_type": "collocation"
    }
  ]
}
```

Once all required information exists, perform the complete reconciliation.

---

# 41. Avoid partial unsafe synchronization

Prefer a calculate-then-apply design.

If semantic classification is required, do not mutate half of the collection and then stop waiting for LLM data.

Instead:

```text
collect source state
       ↓
calculate POS
       ↓
determine semantic classifications needed
       ↓
request missing classifications
       ↓
receive classifications
       ↓
calculate complete desired state
       ↓
calculate mutation plan
       ↓
apply plan
```

This keeps synchronization predictable.

---

# 42. `dry_run`

Support:

```json
{
  "dry_run": true
}
```

Dry run should calculate what would happen without modifying Anki.

If semantic classifications are missing, OpenCode may still need to supply them before the complete dry-run plan can be produced.

Example final plan:

```text
Vocabulary:
  create: 3
  update: 1
  delete: 2
  retag: 6

Kanji:
  create: 4
  update: 0
  delete: 1

Semantic classifications:
  new mimetics: 2
  constructions: 1
  idioms: 1
  collocations: 2

Warnings:
  unmatched JMdict: ...
```

---

# 43. Required MCP tools

Implement at least:

```text
jp_index_dictionaries
jp_index_status
jp_sync
jp_extract_kanji
jp_lookup_vocabulary
jp_lookup_kanji
jp_discover_dictionaries
```

`jp_sync` is the simple primary workflow. It handles both vocabulary classification and kanji extraction.

---

# 44. `jp_index_dictionaries`

Inputs approximately:

```json
{
  "jmdict_path": "...",
  "kanjidic_path": "...",
  "force": false
}
```

Allow either dictionary path to be omitted.

Responsibilities:

* validate XML type;
* stream-parse XML;
* build compact SQLite index;
* create lookup indexes;
* record source metadata;
* return counts and warnings.

This is the normal place where XML is parsed.

---

# 45. `jp_index_status`

Return:

```text
JMdict index:
  present
  schema version
  entry/form counts
  source metadata

KANJIDIC index:
  present
  schema version
  kanji count
  source metadata
```

---

# 46. `jp_classify_vocabulary`

Perform the Vocabulary portion of synchronization.

It should:

1. inspect source notes;
2. mirror/update Vocabulary if necessary;
3. perform JMdict POS classification;
4. determine which entries need semantic LLM classification;
5. consume supplied semantic classifications;
6. apply final tags.

It should support the same semantic-classification handshake as `jp_sync`.

---

# 47. `jp_extract_kanji`

Recalculate:

```text
Japanese::Kanji
```

from the current Vocabulary collection.

Use KANJIDIC SQLite.

Perform:

* creation;
* updating;
* deletion of unreferenced managed kanji;
* deduplication.

---

# 48. `jp_lookup_vocabulary`

This should return JMdict-derived POS information and, when available, stored semantic classification.

Example:

```text
jp_lookup_vocabulary("ぐっすり")
```

might return:

```json
{
  "entry": "ぐっすり",
  "jmdict": {
    "found": true,
    "pos_tags": [
      "jp-organizer::pos::adverb"
    ]
  },
  "semantic": {
    "classified": true,
    "mimetic": true,
    "expression_type": null
  }
}
```

JMdict information must come from SQLite.

---

# 49. `jp_lookup_kanji`

Example:

```text
jp_lookup_kanji("食")
```

could return:

```json
{
  "found": true,
  "entry": "食",
  "meanings": [
    "eat",
    "food"
  ],
  "readings": {
    "on": [
      "ショク"
    ],
    "kun": [
      "た.べる"
    ],
    "nanori": []
  }
}
```

Use SQLite only.

---

# 50. Structured missing-index errors

Return machine-readable results.

Example:

```json
{
  "ok": false,
  "error": {
    "code": "JMDICT_INDEX_MISSING",
    "required_dictionary": "jmdict",
    "message": "JMdict SQLite index is missing.",
    "suggested_action": "Locate JMdict XML and call jp_index_dictionaries."
  }
}
```

Likewise:

```text
KANJIDIC_INDEX_MISSING
```

OpenCode should recognize these conditions and attempt automatic recovery.

---

# 51. Anki integration

Use **AnkiConnect**.

Architecture:

```text
OpenCode
   │
   │ MCP
   ▼
jp-organizer
   │
   ├── JMdict SQLite
   ├── KANJIDIC SQLite
   ├── organizer state
   │
   │ HTTP/JSON
   ▼
AnkiConnect
   │
   ▼
Anki
```

Do not use Python's Anki collection package as the primary backend.

Do not manipulate `collection.anki2` directly.

Keep Anki access behind an adapter/repository interface so another backend could theoretically be implemented later.

---

# 52. Anki failures

Return clear errors for:

* Anki not running;
* AnkiConnect unavailable;
* incorrect AnkiConnect endpoint;
* AnkiConnect errors;
* missing source deck.

Do not expose opaque stack traces as normal MCP results.

---

# 53. Performance

JMdict and KANJIDIC can be large.

Requirements:

* streaming XML parsing;
* SQLite transactions;
* batch inserts;
* indexes on lookup columns;
* batch AnkiConnect operations where practical;
* batch KANJIDIC queries;
* no XML scanning during normal synchronization;
* no unnecessary LLM classification of unchanged entries.

---

# 54. Logging

Log to stderr.

Never corrupt stdio MCP traffic by printing logs to stdout.

Support at least:

```text
INFO
DEBUG
```

Do not log huge note bodies or sensitive unrelated Anki content.

---

# 55. Configuration

Support configuration for:

```text
AnkiConnect URL
AnkiConnect timeout
data/index directory
managed root deck
Vocabulary subdeck
Kanji subdeck
```

Default decks:

```text
Japanese::Vocabulary
Japanese::Kanji
```

Dictionary paths used successfully for indexing may also be stored for future rebuilds.

---

# 56. Tests — JMdict

Use a small JMdict fixture with representative entries.

Test:

* noun;
* verb;
* adjective;
* adverb;
* multi-POS entry;
* unmatched entry.

Verify simplified POS mapping.

The LLM must NOT be involved in these unit tests.

---

# 57. Tests — KANJIDIC

Use a tiny fixture.

Verify:

* literal;
* English meanings;
* on readings;
* kun readings;
* nanori.

---

# 58. Tests — semantic classification protocol

Automated tests should test the protocol, JMdict-first resolution, and application behavior.

Test:

1. an entry with explicit JMdict `on-mim` is classified as mimetic without LLM request;
2. an entry with explicit JMdict `id` is classified as idiom without LLM request;
3. an entry with generic JMdict `exp` POS causes a semantic classification request;
4. an entry absent from JMdict causes a semantic classification request;
5. supplied `mimetic=true` produces only the correct managed mimetic kind tag;
6. `expression_type=construction` produces the construction kind tag;
7. `expression_type=idiom` produces the idiom kind tag;
8. `expression_type=collocation` produces the collocation kind tag;
9. invalid expression types are rejected;
10. unchanged entries reuse cached classifications;
11. modified entries invalidate cached semantic classification;
12. forced reclassification requests new classifications;
13. unrelated tags are preserved;
14. a mimetic may also have POS tags;
15. an idiom may also have POS tags;
16. a collocation may also have POS tags;
17. changing `primary_class` moves the card instead of duplicating it;
18. POS changes alone do not duplicate or move notes.

Use mocked semantic classifications in tests.

Do not make automated test success dependent on calling a live LLM.

---

# 59. Semantic classification examples for README/tests

Include examples demonstrating the intended model behavior.

```text
どきどき
→ mimetic = true
→ expression_type = null
```

```text
ぐっすり
→ mimetic = true
→ expression_type = null
```

```text
すっきり
→ mimetic = true
→ expression_type = null
```

```text
〜ことになる
→ mimetic = false
→ expression_type = construction
```

```text
〜わけではない
→ mimetic = false
→ expression_type = construction
```

```text
顔が広い
→ mimetic = false
→ expression_type = idiom
```

```text
頭が切れる
→ mimetic = false
→ expression_type = idiom
```

```text
約束を守る
→ mimetic = false
→ expression_type = collocation
```

```text
興味を持つ
→ mimetic = false
→ expression_type = collocation
```

These are examples of the intended taxonomy, not a complete hardcoded dictionary.

Do not implement these classifications as a lookup table merely to pass tests.

---

# 60. Sync tests

Mock AnkiConnect.

Test:

1. initial vocabulary creation;
2. repeated sync produces no duplicate notes;
3. adding a source entry creates one managed Vocabulary item;
4. deleting it removes only its managed mirror;
5. modifying it updates the managed mirror;
6. POS tags are refreshed from JMdict;
7. semantic tags are applied from supplied LLM results;
8. stale managed tags are removed;
9. unrelated tags survive;
10. duplicate Kanji cards are not created;
11. shared kanji remain if still referenced;
12. unreferenced managed kanji are removed;
13. unmanaged notes are never deleted;
14. dry run makes no changes.

---

# 61. End-to-end fixture

Use example vocabulary such as:

```text
学生
食べる
きれい
ゆっくり
ぐっすり
顔が広い
約束を守る
〜ことになる
```

Expected JMdict-first behavior:

```text
ぐっすり
→ JMdict has on-mim → mimetic (no LLM)

顔が広い
→ JMdict has exp but no id → LLM fallback → idiom

約束を守る
→ JMdict has exp but no id → LLM fallback → collocation

〜ことになる
→ JMdict has exp but no id → LLM fallback → construction
```

Verify that POS still comes independently from JMdict for all entries.

Verify that entries with decisive JMdict semantic markers do not appear in LLM requests.

---

# 62. README requirements

Create a thorough `README.md`.

It must explain the complete system.

Include:

## Architecture

```text
                         OpenCode
                    ┌───────┴────────┐
                    │                │
                 MCP calls      LLM semantic
                    │          classification
                    ▼                │
               jp-organizer ◄────────┘
                    │
          ┌─────────┼──────────┐
          │         │          │
          ▼         ▼          ▼
       JMdict    KANJIDIC    state DB
       SQLite     SQLite
          │
          │ Anki operations
          ▼
      AnkiConnect
          │
          ▼
         Anki
```

## Classification architecture

Explicitly explain:

```text
POS:
JMdict → SQLite → deterministic mapping

Kind/deck:
JMdict semantic metadata first
        ↓
  sufficiently specific?
     ├── yes → use JMdict
     └── no  → client LLM fallback
        ↓
  primary_class
        ↓
  one vocabulary leaf deck
        ↓
  one kind tag
```

Explain why these use different mechanisms.

Explicitly explain:

> Vocabulary deck placement is mutually exclusive. Every managed vocabulary note has exactly one primary kind and lives in exactly one vocabulary leaf deck.

Also explicitly explain:

> POS tags are independent of the vocabulary kind/deck classification. POS is derived from JMdict for all vocabulary items.

---

# 63. README — explain mimetics

Include the definition from this specification and examples such as:

```text
どきどき
ぐっすり
ぺらぺら
すっきり
ぼんやり
さっぱり
あっさり
```

Explain that mimetics can have an ordinary POS simultaneously.

---

# 64. README — explain expressions

Explain all three categories.

## Construction

Reusable pattern with replaceable slots:

```text
〜ことになる
〜わけではない
〜に違いない
Xもクソもない
```

## Idiom

Fixed/conventional phrase whose meaning is not straightforwardly compositional:

```text
顔が広い
頭が切れる
手を抜く
足を引っ張る
猫の手も借りたい
```

## Collocation

Conventional lexical combination with mostly compositional meaning:

```text
約束を守る
風邪を引く
興味を持つ
責任を取る
```

Explain the distinctions clearly.

---

# 65. README — index lifecycle

Document:

```text
valid SQLite exists
       ↓
use it

SQLite missing/invalid
       ↓
MCP reports missing index
       ↓
OpenCode searches for XML
       ↓
jp_index_dictionaries
       ↓
retry operation
```

Make clear that XML parsing is not part of ordinary vocabulary lookup.

---

# 66. README — MCP tools

For every tool document:

* purpose;
* parameters;
* output;
* whether it modifies Anki;
* example use.

Especially explain the semantic-classification handshake performed by `jp_sync`.

---

# 67. README — sample prompts

Include natural-language examples.

```text
Organize my Anki deck called "Japanese Inbox".
```

```text
Synchronize Japanese Inbox with my Japanese Vocabulary and Kanji decks.
```

```text
I've added and removed some cards from Japanese Inbox. Update everything.
```

```text
Show me what would change if you synchronized Japanese Inbox, but don't modify Anki.
```

```text
Reclassify all mimetics and expressions in Japanese Inbox.
```

```text
Look up the POS information jp-organizer has for 食べる.
```

```text
Show me the KANJIDIC information jp-organizer has for 食.
```

```text
Build the Japanese dictionary indexes using the JMdict and KANJIDIC XML files on this machine.
```

Explain how OpenCode translates these requests into MCP calls and performs semantic classification automatically.

---

# 68. OpenCode configuration

Show how to configure the project as a local stdio MCP server using the CURRENT OpenCode configuration format.

Do not invent syntax.

Inspect current OpenCode documentation/environment while implementing.

---

# 69. Dictionary licensing

Document where JMdict and KANJIDIC come from and their applicable licensing/attribution requirements.

Do not bundle large dictionary datasets unless redistribution is clearly appropriate.

The user supplies local dictionary files.

---

# 70. Recommended project structure

Use a clean architecture approximately like:

```text
jp-organizer/
├── pyproject.toml
├── README.md
├── src/
│   └── jp_organizer/
│       ├── server.py
│       ├── config.py
│       ├── models.py
│       │
│       ├── anki/
│       │   ├── client.py
│       │   └── repository.py
│       │
│       ├── dictionaries/
│       │   ├── jmdict_indexer.py
│       │   ├── jmdict_repository.py
│       │   ├── kanjidic_indexer.py
│       │   └── kanjidic_repository.py
│       │
│       ├── organizer/
│       │   ├── pos_classifier.py
│       │   ├── semantic.py
│       │   ├── kanji.py
│       │   ├── reconciliation.py
│       │   └── service.py
│       │
│       └── state/
│           └── repository.py
│
└── tests/
    ├── fixtures/
    ├── test_jmdict.py
    ├── test_kanjidic.py
    ├── test_indexes.py
    ├── test_semantic_protocol.py
    ├── test_classifier.py
    └── test_sync.py
```

The exact layout may differ.

Preserve separation between:

* MCP interface;
* Anki integration;
* dictionary indexing;
* deterministic POS classification;
* LLM semantic-classification protocol;
* kanji extraction;
* reconciliation;
* persistent state.

Do not place the complete implementation in `server.py`.

---

# 71. Core implementation principles

Prioritize, in order:

1. data safety;
2. deterministic POS classification;
3. clearly defined LLM semantic classification;
4. idempotency;
5. reconciliation instead of fragile event tracking;
6. ownership-safe deletion;
7. SQLite dictionary lookup;
8. avoiding repeated LLM work;
9. simple MCP interfaces;
10. testability;
11. performance;
12. understandable architecture.

---

# 72. Important classification rules

These are hard requirements.

### POS

```text
JMdict only
```

The LLM does not determine POS tags.

POS tags are independent of the vocabulary kind/deck classification.

### Kanji data

```text
KANJIDIC only
```

The LLM does not invent kanji meanings or readings.

### Mimetics

```text
JMdict first (on-mim marker)
        ↓
    if absent → OpenCode LLM
```

Use semantic understanding rather than surface-form heuristics alone.

### Idioms

```text
JMdict first (id marker)
        ↓
    if absent → OpenCode LLM
```

### Expressions (construction / collocation)

```text
JMdict first (decisive markers)
        ↓
    if insufficient → OpenCode LLM
```

Classify into:

```text
construction
idiom
collocation
none
```

using the definitions in this specification.

### Existing semantic classifications

Reuse them when entry text is unchanged.

If a cached LLM result exists but JMdict now provides a decisive classification, prefer the JMdict result.

### Modified entries

Invalidate and reclassify.

---

# 73. Completion criteria

The project is not complete until all of the following work:

1. MCP server starts over stdio.
2. OpenCode can enumerate tools.
3. JMdict can be indexed into compact SQLite (schema v2 with semantic metadata).
4. KANJIDIC can be indexed into compact SQLite.
5. POS lookup uses JMdict SQLite.
6. Kanji lookup uses KANJIDIC SQLite.
7. Normal sync does not scan XML.
8. Missing indexes are reported structurally.
9. OpenCode can recover by locating XML and indexing it.
10. External source decks can be mirrored to vocabulary leaf decks.
11. `Japanese::Vocabulary` can also be classified in place.
12. POS tags come from JMdict.
13. POS tags are independent of kind/deck classification.
14. Explicit JMdict mimetic markers (`on-mim`) avoid LLM calls.
15. Explicit JMdict idiom markers (`id`) avoid LLM calls.
16. Generic expression metadata (`exp`) falls back to OpenCode LLM.
17. Semantic classifications are validated by the MCP server.
18. Semantic classifications are cached with source tracking (`jmdict` vs `llm`).
19. Unchanged entries do not require repeated LLM classification.
20. Modified entries do require semantic reclassification.
21. Stale managed tags are removed.
22. Unrelated user tags remain intact.
23. Kanji are extracted from all vocabulary leaf decks.
24. Kanji notes contain Entry, Meanings, and Readings.
25. Duplicate Kanji cards are prevented.
26. Source additions propagate.
27. Source edits propagate.
28. Source removals propagate.
29. Shared kanji remain while referenced.
30. Unreferenced managed kanji are removed.
31. Unmanaged Anki notes are never automatically deleted.
32. Repeated sync without changes produces no mutations.
33. Classification changes move cards rather than duplicating notes.
34. Dry-run works.
35. Automated tests pass.
36. README fully explains architecture, deck hierarchy, classification, POS independence, mimetics, expressions, indexing, synchronization, MCP tools, OpenCode behavior, and sample prompts.
37. TASK.md accurately describes the implemented behavior.

---

# 74. Implementation work style

First inspect the repository.

Then:

1. inspect the current official MCP SDK;
2. inspect current OpenCode MCP support/configuration;
3. inspect AnkiConnect's current API;
4. inspect the actual JMdict format/entity definitions;
5. inspect the actual KANJIDIC format;
6. summarize the intended architecture briefly;
7. implement the complete project;
8. run tests;
9. fix failures;
10. run configured lint/type checks;
11. provide a concise final summary.

Do not stop after scaffolding.

Do not leave essential behavior as TODOs.

Do not invent OpenCode/MCP/AnkiConnect interfaces when they can be verified.

Where the real JMdict, KANJIDIC, MCP SDK, OpenCode, or AnkiConnect APIs differ from assumptions in this specification, adapt to the actual APIs while preserving the required behavior.
