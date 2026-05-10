# Endpoint Cheatsheet

Flat URL / verb table. Pair with `read-operations.md`, `create-operations.md`, `update-operations.md`, `delete-operations.md` for working examples.

## Read endpoints (Local API)

```
GET localhost:23119/api/users/{ID}/items?q=QUERY&limit=N
GET localhost:23119/api/users/{ID}/items/ITEMKEY
GET localhost:23119/api/users/{ID}/items/ITEMKEY/children
GET localhost:23119/api/users/{ID}/collections
GET localhost:23119/api/users/{ID}/collections/COLLKEY/items
GET localhost:23119/api/users/{ID}/tags
GET localhost:23119/api/users/{ID}/items/trash
```

Headers: `Zotero-Allowed-Request: true`, optionally `Zotero-API-Version: 3`.

## Write endpoints (Web API)

```
POST   api.zotero.org/users/{ID}/items                  (create)
POST   api.zotero.org/users/{ID}/collections            (create collection)
PATCH  api.zotero.org/users/{ID}/items/ITEMKEY          (update)
DELETE api.zotero.org/users/{ID}/items/ITEMKEY          (delete)
DELETE api.zotero.org/users/{ID}/items?itemKey=K1,K2    (batch delete)
```

Headers: `Zotero-API-Key: <key>`, `Content-Type: application/json`.

For full request/response shapes, see `api-reference.md`.
