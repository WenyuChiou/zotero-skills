# MERGE Duplicates (Web API, no native endpoint)

The Zotero Web API has no `POST /items/merge` or similar call. Only the
Zotero desktop app's "Merge Items" pane does this in one click. An agent
that concludes "the API can't merge, so this has to be done by hand" is
wrong: the CORE of the desktop merge is just a sequence of ordinary writes,
and that same sequence works over the Web API. It is not the full desktop
merge, though; see "What this does NOT do" below before relying on it for
anything beyond that core.

## What this reproduces (the core of the desktop merge)

1. Pick a "master" item (the one to keep) and one duplicate.
2. Move every child of the duplicate (notes, attachments) onto the master.
3. Union the duplicate's collections, tags, and own relations onto the
   master.
4. Record the relationship (so sync and other tools can tell a merge
   happened) via a `dc:replaces` relation on the master pointing at the
   duplicate.
5. Trash the duplicate (not a permanent delete).

## What this does NOT do (vs. the full desktop merge)

- **Does not repoint other items' relations that reference the duplicate.**
  If some other item in the library has a relation pointing at `dup_key`,
  it still points at a now-trashed item after this call; fix those by hand
  if any are known.
- **Does not reconcile `dateAdded`.** The desktop merge keeps the earliest
  `dateAdded` of the two; this call leaves the keeper's `dateAdded`
  untouched.
- **Does not deduplicate identical PDF attachments.** If both the keeper
  and the duplicate already had their own copy of the same PDF, the keeper
  ends up with both as sibling attachments; removing the redundant one is
  a separate, manual step.

## Use the helper

```python
from zotero_client import ZoteroDualClient

dual = ZoteroDualClient()

# Confirm with the user FIRST: show both keys + titles. This call trashes
# the duplicate as its last step.
summary = dual.merge_duplicates(keep_key="KEEPKEY", dup_key="DUPKEY")
print(summary)
# {"children_moved": 2, "skipped_deleted_children": [],
#  "collections_added": ["COLLB"], "tags_added": ["new-tag"],
#  "relation": "http://zotero.org/users/.../items/DUPKEY", "trashed_key": "DUPKEY"}
```

`merge_duplicates()`:

- **Refuses** `keep_key == dup_key`, including two differently-cased
  spellings of the same key (pyzotero / the Web API upper-case keys, so
  the raw strings can differ while the server resolves them to the same
  item); that would just trash the keeper.
- **Refuses** if either item is a note, an attachment, or has a
  `parentItem` set; only top-level library items can be merged.
- **Refuses** if either item is already deleted/trashed -- call
  `restore_item()` on it first, or pick a different pair.
- **Refuses** on an identity mismatch, unless you explicitly pass
  `require_same_doi=False` (do that only after the user confirms by hand
  that the two records really are the same work, e.g. a preprint vs. the
  published version): DOIs are normalized (stripped; a leading
  `doi.org`/`dx.doi.org` resolver URL in any scheme/case, or a `doi:`
  prefix with or without a following space, dropped; then lowercased)
  and must match when at least one side has one. When BOTH are empty,
  the normalized title AND `itemType` must match, and EITHER the year
  or the first creator's last name must also match -- a shared generic
  title like "Introduction" is not enough on its own.
- Reads both items from the **Web API** (the authoritative version
  source, matching every other write in this client).
- Moves every (non-trashed) child of the duplicate onto the keeper by
  setting the child's `parentItem`, paginating with pyzotero's
  `everything()` so a duplicate with more than about 100 children is not
  silently truncated. A child that is ALREADY in the trash is skipped
  (pyzotero's `update_item` rejects a payload carrying a `deleted` key)
  and listed in the returned `skipped_deleted_children`, not silently
  dropped.
- If moving a child raises partway through, the error is wrapped in a
  `ZoteroWriteError` that lists which child keys were already moved.
  Nothing has been trashed yet at that point, so re-running the call once
  the underlying problem is fixed is safe.
- Re-reads the keeper fresh, right before writing it, so the union below
  is based on its latest version rather than a copy that may have gone
  stale while children were being moved.
- Unions the duplicate's collections, tags, and OWN relations (any
  predicate, not just `dc:replaces`; a bare string is normalized to a
  one-item list; no duplicates) onto the keeper. Nothing the keeper
  already had is dropped. A relation value pointing back at the KEEPER
  itself is skipped: Zotero's "Related" links are two-way, so the
  duplicate commonly already has one pointing at the keeper, and copying
  it over would leave the keeper related to itself.
- Adds the real Zotero item URI to the keeper's `relations['dc:replaces']`:
  `http://zotero.org/users/<libraryID>/items/<dup_key>` for a user
  library, `http://zotero.org/groups/<libraryID>/items/<dup_key>` for a
  group library. Never the singular "user"/"group".
- Calls `trash_item(dup_key)` **last**, once nothing useful is left on the
  duplicate. A failure updating the keeper, or trashing the duplicate, is
  also wrapped in `ZoteroWriteError`, stating plainly what has and has
  not happened (children are moved either way; a keeper-update failure
  means nothing was trashed; a trash failure means the keeper WAS
  updated but the duplicate still needs trashing by hand).

## Safety

- This is a delete, under this skill's safety rules: show the user both
  item keys and titles (which one is kept, which one is trashed) and get
  explicit confirmation before calling `merge_duplicates()`.
- The trash step is recoverable for about 30 days if the merge turns out
  to be wrong (`restore_item()` reverses it); a permanent `delete_item()`
  is never used here.
- Do the identity check with `require_same_doi=True` (the default) unless
  the user has already confirmed the two records are the same work.

## Manual fallback

```python
import re
from zotero_client import get_client, ZoteroDualClient

zot = get_client()

keep = zot.item("KEEPKEY")
dup = zot.item("DUPKEY")

# 0) the refusals merge_duplicates() does for you
if str(keep["data"]["key"]).upper() == str(dup["data"]["key"]).upper():
    raise ValueError("cannot merge an item with itself")
for label, item in (("keep", keep), ("dup", dup)):
    d = item["data"]
    if d.get("parentItem") or d.get("itemType") in ("note", "attachment"):
        raise ValueError(f"{label} is a child item; only top-level items can be merged")
if keep["data"].get("deleted") or dup["data"].get("deleted"):
    raise ValueError("one of these is already trashed; restore it first")

DOI_PREFIX_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
def norm_doi(doi):
    return DOI_PREFIX_RE.sub("", (doi or "").strip(), count=1).strip().lower()
def norm_title(title):
    return re.sub(r"\s+", " ", (title or "").strip().lower())

keep_doi, dup_doi = norm_doi(keep["data"].get("DOI")), norm_doi(dup["data"].get("DOI"))
if keep_doi or dup_doi:
    if keep_doi != dup_doi:
        raise ValueError(f"DOI mismatch: {keep_doi!r} vs {dup_doi!r}")
else:
    keep_title, dup_title = norm_title(keep["data"].get("title")), norm_title(dup["data"].get("title"))
    same_type = keep["data"].get("itemType") == dup["data"].get("itemType")
    keep_year = re.search(r"\d{4}", keep["data"].get("date") or "")
    dup_year = re.search(r"\d{4}", dup["data"].get("date") or "")
    same_year = bool(keep_year and dup_year and keep_year.group() == dup_year.group())
    keep_creators, dup_creators = keep["data"].get("creators") or [], dup["data"].get("creators") or []
    same_creator = bool(keep_creators and dup_creators and
                         (keep_creators[0].get("lastName") or "").strip().lower()
                         == (dup_creators[0].get("lastName") or "").strip().lower())
    if not (keep_title and keep_title == dup_title and same_type and (same_year or same_creator)):
        raise ValueError("neither item has a DOI, and title/itemType/year/creator do not match closely enough")

# 1) move children
for child in zot.everything(zot.children("DUPKEY")):
    if child["data"].get("deleted"):
        continue  # already trashed; update_item would reject it
    child["data"]["parentItem"] = "KEEPKEY"
    zot.update_item(child["data"])

# 2) union collections + tags (re-read keep first in case it changed)
keep = zot.item("KEEPKEY")
keep["data"]["collections"] = list(set(keep["data"].get("collections", []))
                                    | set(dup["data"].get("collections", [])))
existing_tags = {t["tag"] for t in keep["data"].get("tags", [])}
keep["data"].setdefault("tags", []).extend(
    t for t in dup["data"].get("tags", []) if t["tag"] not in existing_tags
)

# 3) union ALL of dup's own relations onto keep (skip any pointing at keep
# itself -- Zotero's "Related" links are two-way, so dup commonly already
# has one pointing back at keep), then add the dc:replaces relation for
# the merge itself.
relations = keep["data"].setdefault("relations", {})
# zot.library_type is already "users"/"groups" here (pyzotero appends the
# "s" internally), so this already produces the real shape, e.g.
# http://zotero.org/users/<id>/items/DUPKEY. Never build this from a
# singular "user"/"group" string.
keep_uri = f"http://zotero.org/{zot.library_type}/{zot.library_id}/items/KEEPKEY"
dup_uri = f"http://zotero.org/{zot.library_type}/{zot.library_id}/items/DUPKEY"
for predicate, values in (dup["data"].get("relations") or {}).items():
    values = [values] if isinstance(values, str) else list(values)
    existing = relations.get(predicate, [])
    if isinstance(existing, str):
        existing = [existing]
    merged = list(existing)
    for v in values:
        if v == keep_uri:
            continue  # would make keep related to itself
        if v not in merged:
            merged.append(v)
    relations[predicate] = merged
existing_replaces = relations.get("dc:replaces", [])
if isinstance(existing_replaces, str):
    existing_replaces = [existing_replaces]
if dup_uri not in existing_replaces:
    existing_replaces = [*existing_replaces, dup_uri]
relations["dc:replaces"] = existing_replaces
zot.update_item(keep["data"])

# 4) trash the duplicate LAST (recoverable)
ZoteroDualClient().trash_item("DUPKEY")
```
