# AI Instructions: Protocol Documentation Review & Consolidation

**Purpose**: Instructions for reviewing and tidying the `protocol_docs/` directory.

---

## Goals

1. **Minimize file count** - Consolidate related content into single documents
2. **Avoid repetition** - Each piece of information should exist in ONE place only
3. **Maintain cross-references** - Ensure documents link to each other correctly
4. **Keep authoritative sources** - Each topic should have ONE authoritative document

---

## Step 1: Inventory Check

First, understand what exists:

```bash
# Count lines per file, sorted by size
wc -l /home/will/source/lednetwf_ble/protocol_docs/*.md | sort -n

# List all doc files
ls -la /home/will/source/lednetwf_ble/protocol_docs/*.md
```

**Red flags:**
- Any single document over 600 lines is a candidate for being too large
- Documents with very similar names may have overlapping content
- Gaps in numbering (e.g., missing 11, 12, 13, 14) may indicate previous consolidation

---

## Step 2: Check INDEX.md

Read `protocol_docs/INDEX.md` to understand:
- What files should exist (Document Index table)
- What each file's purpose is (Description column)
- Current version number

**Check for:**
- Links to files that don't exist (broken links)
- Files that exist but aren't in the index
- Outdated descriptions

---

## Step 3: Identify Duplication

### Method A: Grep for Topic Keywords

```bash
# Example: Find all files discussing BLE advertisement parsing
grep -l "manufacturer.*data\|advertisement\|mfr_data" /home/will/source/lednetwf_ble/protocol_docs/*.md

# Example: Find all files discussing mic/microphone
grep -l "mic\|microphone\|sound.*reactive" /home/will/source/lednetwf_ble/protocol_docs/*.md

# Example: Find all files with Python code examples
grep -l "```python" /home/will/source/lednetwf_ble/protocol_docs/*.md
```

### Method B: Check Cross-References

```bash
# Find all internal doc references
grep -oh "\\[.*\\](.*\\.md)" /home/will/source/lednetwf_ble/protocol_docs/*.md | sort | uniq -c | sort -rn

# Find broken references (references to non-existent files)
for ref in $(grep -oh "[0-9]*_[a-z_]*\\.md" /home/will/source/lednetwf_ble/protocol_docs/*.md | sort -u); do
    if [ ! -f "/home/will/source/lednetwf_ble/protocol_docs/$ref" ]; then
        echo "BROKEN: $ref"
    fi
done
```

### Common Duplication Patterns

| Topic | Should Live In | Often Duplicated In |
|-------|----------------|---------------------|
| BLE advertisement formats | 02_manufacturer_data.md | 17_device_configuration.md |
| Product ID mapping | 03_device_identification.md | 10_device_specific.md |
| Mic detection | 18_sound_reactive_music_mode.md | 17_device_configuration.md |
| Effect commands | 06_effect_commands.md | 07_effect_names.md |
| Transport layer | 04_connection_transport.md | 08_state_query_response_parsing.md |

---

## Step 4: Consolidation Strategy

### When Content is Duplicated

1. **Identify the authoritative document** - Usually the one with more detail or the one whose title matches the topic
2. **Merge into authoritative** - Copy additional details from the duplicate
3. **Remove from duplicate** - Delete the duplicated section
4. **Add cross-reference** - Replace removed section with link to authoritative doc

### Example Consolidation Pattern

Before (in doc 17):
```markdown
## BLE Advertisement Parsing
[500 lines of content that also exists in doc 02]
```

After (in doc 17):
```markdown
## Related Documentation

- **BLE Advertisement Parsing**: See [02_manufacturer_data.md](02_manufacturer_data.md)
```

### When a Document is Too Large

Signs a document needs splitting:
- Over 600-800 lines
- Multiple unrelated major sections
- Different device types mixed together

Split strategy:
- Keep core topic in original document
- Move specialized topics to existing specialized docs
- Create new doc only if no suitable home exists

---

## Step 5: Update INDEX.md

After consolidation:

1. **Update version number** (increment by 0.1)
2. **Update date**
3. **Update descriptions** if document scope changed
4. **Remove entries** for deleted files
5. **Add version history entry** describing changes

Example version history entry:
```markdown
| 7 Dec 2025 | v3.8 - Consolidated BLE parsing into doc 02, mic detection into doc 18 |
```

---

## Step 6: Verify Results

```bash
# Recount lines - should be fewer total
wc -l /home/will/source/lednetwf_ble/protocol_docs/*.md | sort -n

# Check for broken links again
grep -oh "\\[.*\\]([^)]*\\.md)" /home/will/source/lednetwf_ble/protocol_docs/*.md | \
  sed 's/.*(\(.*\))/\1/' | sort -u | \
  while read f; do
    [ ! -f "/home/will/source/lednetwf_ble/protocol_docs/$f" ] && echo "BROKEN: $f"
  done

# Verify INDEX lists all docs
ls protocol_docs/*.md | xargs -I{} basename {} | sort > /tmp/actual
grep -oP '\d+_[a-z_]+\.md' protocol_docs/INDEX.md | sort > /tmp/indexed
diff /tmp/actual /tmp/indexed
```

---

## Document Authority Map

| Topic | Authoritative Document |
|-------|------------------------|
| BLE advertisement parsing | 02_manufacturer_data.md |
| Product ID → capabilities | 03_device_identification.md |
| Transport layer / wrapping | 04_connection_transport.md |
| RGB/CCT/brightness commands | 05_basic_commands.md |
| Effect commands (all formats) | 06_effect_commands.md |
| Effect name lists | 07_effect_names.md |
| State query & responses | 08_state_query_response_parsing.md |
| Python implementation | 09_python_guide.md |
| Device quirks by product | 10_device_specific.md |
| Static effects with FG+BG | 15_static_effects_with_bg_color.md |
| Symphony query formats | 16_query_formats_0x63_vs_0x44.md |
| Device config (color order, LED count) | 17_device_configuration.md |
| Sound reactive / mic mode | 18_sound_reactive_music_mode.md |

---

## Common Issues Found

### Issue: Document Numbers Don't Match Content

Example: Doc 17 titled "device_configuration" but contains BLE advertisement formats.

**Fix**: Move content to appropriate document based on topic, not number.

### Issue: Same Code Example in Multiple Docs

Example: Product ID extraction `(mfr_data[8] << 8) | mfr_data[9]` in 4 files.

**Fix**: Keep in authoritative doc (02), reference from others.

### Issue: Broken Cross-References

Example: Reference to "12_symphony_effect_names.md" when file was renamed to "07_effect_names.md".

**Fix**: Search and replace old name with new name.

### Issue: Outdated INDEX Description

Example: INDEX says doc 02 covers "27 bytes" but doc now covers multiple formats.

**Fix**: Update description to match actual content.

---

## Checklist

- [ ] Line count inventory taken
- [ ] INDEX.md reviewed for broken links
- [ ] Duplication identified between docs
- [ ] Content consolidated into authoritative docs
- [ ] Cross-references added where content was removed
- [ ] INDEX.md version/date/descriptions updated
- [ ] Final line count verified (should be lower)
- [ ] No broken links remain
