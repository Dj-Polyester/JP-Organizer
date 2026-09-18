# JP-organizer

**JP-organizer** is a production-quality MCP server for organizing Japanese-learning flashcards in Anki.

It connects to Anki via [AnkiConnect](https://git.sr.ht/~foosoft/anki-connect), indexes [JMdict](http://www.edrdg.org/jmdict/j_jmdict.html) and [KANJIDIC](http://www.edrdg.org/wiki/index.php/KANJIDIC_Project) into compact SQLite databases, and uses a hybrid classification system to automatically tag vocabulary and extract kanji.

**Client-agnostic:** This is a standard MCP server using stdio transport. It works with any MCP-capable client — OpenCode, Claude Desktop, Cline, Cursor, or any other host that supports the Model Context Protocol.

## Architecture

```text
                      MCP Client / LLM
                    ┌───────┴────────┐
                    │                │
                 MCP calls      LLM semantic
                      │          classification (fallback only)
                      ▼                │
                 JP-organizer ◄────────┘
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

## How it works

JP-organizer talks to the **Anki desktop app running on your computer** via the AnkiConnect add-on. It does **not** connect to AnkiWeb directly and does **not** need your AnkiWeb email or password.

### Where the decks appear

The managed decks are created in your **local Anki application** — the same Anki window you already use for studying. You will see them in the deck list on the left side of Anki's main window.

### Permanent deck hierarchy

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
- `Japanese::Vocabulary::Words`
- `Japanese::Vocabulary::Mimetics`
- `Japanese::Vocabulary::Expressions::Constructions`
- `Japanese::Vocabulary::Expressions::Idioms`
- `Japanese::Vocabulary::Expressions::Collocations`
- `Japanese::Vocabulary::Other`
- `Japanese::Kanji`

**Vocabulary deck placement is mutually exclusive.** Every managed vocabulary note has exactly one primary kind and lives in exactly one vocabulary leaf deck.

### AnkiWeb sync

If you already use AnkiWeb to sync between devices, nothing changes. Anki's built-in sync (the sync button in the top-right corner of Anki) pushes your local collection — including the new decks and cards created by JP-organizer — to AnkiWeb. From there, they sync to your phone, tablet, or other computers just like any other deck.

JP-organizer never touches AnkiWeb credentials. It only talks to the local Anki instance.

### Prerequisites

1. **Anki must be running** on your computer
2. **AnkiConnect add-on** must be installed (Tools → Add-ons → Get Add-ons → code `2055492159`)
3. **AnkiConnect must be enabled** (a green checkmark appears when Anki starts)
4. (Optional) **JMdict and KANJIDIC XML files** for dictionary indexing

## Classification architecture

### Two independent dimensions

```text
Kind/deck:       mutually exclusive
POS:             independent metadata
```

### POS (Part of Speech)

```text
JMdict → SQLite → deterministic mapping → jp-organizer::pos::* tags
```

POS tags come **only** from JMdict. The LLM does not determine POS tags.

POS tags are **independent** of the vocabulary kind/deck classification. POS is derived from JMdict for **all** vocabulary items, regardless of their primary class.

Example:

```text
ぐっすり

deck:
  Japanese::Vocabulary::Mimetics

tags:
  jp-organizer::kind::mimetic
  jp-organizer::pos::adverb
```

### Kind / primary class

```text
JMdict semantic metadata
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

Every managed vocabulary entry has exactly one `primary_class`:

| primary_class | Deck | Kind tag |
|---------------|------|----------|
| `word` | `Japanese::Vocabulary::Words` | `jp-organizer::kind::word` |
| `mimetic` | `Japanese::Vocabulary::Mimetics` | `jp-organizer::kind::mimetic` |
| `construction` | `Japanese::Vocabulary::Expressions::Constructions` | `jp-organizer::kind::expression::construction` |
| `idiom` | `Japanese::Vocabulary::Expressions::Idioms` | `jp-organizer::kind::expression::idiom` |
| `collocation` | `Japanese::Vocabulary::Expressions::Collocations` | `jp-organizer::kind::expression::collocation` |
| `other` | `Japanese::Vocabulary::Other` | `jp-organizer::kind::other` |

Kanji continues to use:

```text
jp-organizer::kind::kanji
```

### Semantic classification: JMdict-first

The system first attempts to determine semantic classification from JMdict:

- **Explicit mimetic marker** (`on-mim`) → classified as mimetic, no LLM call
- **Explicit idiom marker** (`id`) → classified as idiom, no LLM call
- **Generic expression marker** (`exp`) → expression-like but subtype unresolved → **LLM fallback**
- **Normal lexical item** → word, no LLM call
- **Absent from JMdict** → **LLM fallback**

Only entries that JMdict cannot resolve sufficiently are sent to the client LLM.

## What is a mimetic?

A **mimetic** is a Japanese lexical item that imitates or evokes:

- a sound
- movement
- physical manner
- feeling
- appearance
- state
- texture
- psychological condition
- sensory impression

Examples:

| Entry | Meaning |
|-------|---------|
| どきどき | heart pounding / nervous excitement |
| ぐっすり | sleeping soundly |
| ぺらぺら | fluently, or thin/flapping |
| すっきり | refreshed, clear, uncluttered |
| ぼんやり | vaguely, absent-mindedly, dimly |
| さっぱり | refreshed/clean, completely, or not at all |
| あっさり | lightly, simply, without fuss |

Mimetics retain their ordinary POS tags. For example, **ぐっすり** may be both:

```text
jp-organizer::kind::mimetic
jp-organizer::pos::adverb
```

## Expressions

An **expression** is a multi-word unit, grammatical pattern, or conventional phrase learned as a unit.

### Construction

A reusable grammatical or phraseological pattern with replaceable slots.

Examples:

```text
〜ことになる
〜わけではない
〜に違いない
Xもクソもない
```

Kind tag: `jp-organizer::kind::expression::construction`

### Idiom

A fixed expression whose conventional overall meaning is not straightforwardly predictable from its components.

Examples:

```text
顔が広い  (to be well-connected)
頭が切れる  (sharp-minded)
手を抜く  (to cut corners)
足を引っ張る  (to hold someone back)
猫の手も借りたい  (extremely busy)
```

Kind tag: `jp-organizer::kind::expression::idiom`

### Collocation

A conventional lexical combination whose meaning remains mostly compositional, but Japanese strongly prefers that particular pairing.

Examples:

```text
約束を守る  (keep a promise)
風邪を引く  (catch a cold)
興味を持つ  (have an interest)
責任を取る  (take responsibility)
```

Kind tag: `jp-organizer::kind::expression::collocation`

## Index lifecycle

```text
valid SQLite exists
       ↓
   use it

SQLite missing/invalid
       ↓
MCP reports missing index
       ↓
jp_discover_dictionaries (uses ripgrep)
       ↓
jp_index_dictionaries
       ↓
retry operation
```

XML parsing happens **only** during indexing, not during normal vocabulary lookup.

## MCP Tools

### `jp_index_dictionaries`

Index JMdict and/or KANJIDIC XML files into SQLite.

Parameters:
- `jmdict_path` (optional): path to JMdict XML
- `kanjidic_path` (optional): path to KANJIDIC XML
- `force` (optional): rebuild even if index exists

Returns: counts and status.

### `jp_index_status`

Check whether the indexes exist and their metadata.

Returns: JMdict and KANJIDIC index status.

### `jp_discover_dictionaries`

Search the filesystem for JMdict and KANJIDIC XML files using **ripgrep** (`rg`). Verifies candidate files by inspecting their XML root element.

Returns: candidate paths and verified paths for each dictionary type.

This tool is useful when the indexes are missing and you need to locate dictionary files automatically instead of manually specifying paths.

### `jp_sync`

Primary day-to-day tool. Synchronize a source deck with the Japanese vocabulary and kanji hierarchy.

Parameters:
- `source_deck_name` (required): e.g. `"Japanese Inbox"`
- `entry_field` (optional): which field contains the Japanese entry
- `dry_run` (optional): calculate plan without modifying Anki
- `force_semantic_reclassification` (optional): invalidate cached semantic results
- `semantic_classifications` (optional): LLM classification results

**Semantic classification handshake:**

If `jp_sync` encounters entries needing semantic classification, it returns:

```json
{
  "status": "semantic_classification_required",
  "requests": [
    {"id": "123", "entry": "顔が広い"},
    {"id": "124", "entry": "約束を守る"}
  ]
}
```

Your MCP client should classify each entry and call `jp_sync` again with:

```json
{
  "source_deck_name": "Japanese Inbox",
  "semantic_classifications": [
    {"id": "123", "mimetic": false, "expression_type": "idiom"},
    {"id": "124", "mimetic": false, "expression_type": "collocation"}
  ]
}
```

Note: entries with explicit JMdict mimetic or idiom markers are resolved automatically and do not appear in the requests list.

### `jp_extract_kanji`

Recalculate `Japanese::Kanji` from the current vocabulary collection across all vocabulary leaf decks.

Parameters:
- `dry_run` (optional)

### `jp_lookup_vocabulary`

Look up JMdict POS, semantic classification, and primary class for a single entry.

Parameters:
- `entry` (required)

Returns a JSON object like:

```json
{
  "entry": "ぐっすり",
  "primary_class": "mimetic",
  "target_deck": "Japanese::Vocabulary::Mimetics",
  "kind_tag": "jp-organizer::kind::mimetic",
  "jmdict": {
    "found": true,
    "pos_tags": ["jp-organizer::pos::adverb"],
    "semantic_markers": ["on-mim"]
  },
  "semantic": {
    "mimetic": true,
    "expression_type": null,
    "source": "jmdict"
  }
}
```

### `jp_lookup_kanji`

Look up KANJIDIC meanings and readings for a single kanji.

Parameters:
- `literal` (required)

## Sample prompts

Natural-language examples you can use with any MCP client:

### Day-to-day use

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

### Dictionary lookup

```text
Look up the POS information JP-organizer has for 食べる.
```

```text
Show me the KANJIDIC information JP-organizer has for 食.
```

### First-time setup (automatic discovery)

If dictionary indexes are missing, the client will automatically discover and index them:

```text
Build the Japanese dictionary indexes using the JMdict and KANJIDIC XML files on this machine.
```

The expected automatic flow when indexes are missing:

```text
User: "Organize my Japanese Inbox"
  → jp_sync reports missing index
  → jp_discover_dictionaries finds XML files (uses ripgrep)
  → jp_index_dictionaries builds SQLite indexes
  → jp_sync retries and completes
```

## MCP Client Configuration

### Stdio mode (recommended)

Run JP-organizer as a local stdio subprocess. This is the simplest and most reliable approach.

**OpenCode:**
```bash
opencode mcp add jp-organizer -- uv run --directory /path/to/jp-organizer jp-organizer
```

**Codex:**
```bash
codex mcp add jp-organizer -- uv run --directory /path/to/jp-organizer jp-organizer
```

**Claude Code:**
```bash
claude mcp add jp-organizer uv run --directory /path/to/jp-organizer jp-organizer
```

**Cursor:** Settings → Tools & MCP → "+ Add New MCP Server" → Transport: `stdio`, Command: `uv run --directory /path/to/jp-organizer jp-organizer`

**Cline:** Sidebar → MCP Servers → "+ Add MCP Server" → Command: `uv`, Args: `run --directory /path/to/jp-organizer jp-organizer`

**VS Code:** Command Palette → "MCP: Add Server" → choose Workspace or Global, then enter command: `uv run --directory /path/to/jp-organizer jp-organizer`

**Claude Desktop:** Edit `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "jp-organizer": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/jp-organizer", "jp-organizer"]
    }
  }
}
```

### Remote HTTP mode

Run jp-organizer as a persistent HTTP server:

```bash
uv run jp-organizer --remote --port 8766
```

Then add by URL:

**OpenCode:** `opencode mcp add jp-organizer --url http://127.0.0.1:8766/mcp`

**Codex:** `codex mcp add jp-organizer --url http://127.0.0.1:8766/mcp`

**Cursor:** Settings → Tools & MCP → "+ Add New MCP Server" → Transport: `streamable-http`, URL: `http://127.0.0.1:8766/mcp`

**Claude Desktop:** Settings → Connectors → "Add custom connector" → URL: `http://127.0.0.1:8766/mcp`

**Claude Code:** `claude mcp add jp-organizer --url http://127.0.0.1:8766/mcp`

## AnkiConnect authentication

AnkiConnect requires authentication only if you have configured an API key in AnkiConnect's settings (Tools → Add-ons → AnkiConnect → Config → `apiKey`).

If authentication is enabled, provide the key when starting JP-organizer:

```bash
uv run jp-organizer --anki-connect-key YOUR_API_KEY
```

Or set the `ANKI_CONNECT_KEY` environment variable.

If no key is configured in AnkiConnect, JP-organizer connects without authentication.

## Dictionary licensing

### JMdict

JMdict is copyright © Electronic Dictionary Research and Development Group (EDRDG), and is licensed under the Creative Commons Attribution-ShareAlike Licence (V3.0). See http://www.edrdg.org/edrdg/licence.html for details.

### KANJIDIC

KANJIDIC is also copyright © EDRDG and is available under the same Creative Commons licence.

This project does **not** bundle dictionary data. You must supply your own local XML files.

## Development

Install in development mode:

```bash
uv pip install -e ".[dev]"
```

Run tests:

```bash
uv run pytest tests/ -v
```

## Requirements

- **Python >= 3.14**
- **Anki desktop app** running with the **AnkiConnect** add-on installed
  - Install AnkiConnect: Tools → Add-ons → Get Add-ons → enter code `2055492159`
  - Restart Anki. AnkiConnect starts automatically on port `8765`.
- **Local JMdict and KANJIDIC XML files** for dictionary indexing
  - These are not bundled; download them from [EDRDG](http://www.edrdg.org/)
  - Common filenames: `JMdict_e`, `JMdict_e.xml`, `kanjidic2.xml`
- **ripgrep (`rg`)** (optional, for automatic dictionary discovery)
  - If `rg` is installed, `jp_discover_dictionaries` will search your filesystem for dictionary files automatically.
  - If `rg` is not available, you must provide dictionary paths manually to `jp_index_dictionaries`.