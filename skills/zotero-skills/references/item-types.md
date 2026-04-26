# Zotero Item Types and Fields

## Journal Article

```python
template = zot.item_template("journalArticle")
```

Fields:
- `title` - Article title
- `creators` - List of authors
- `abstractNote` - Abstract
- `publicationTitle` - Journal name
- `volume` - Volume number
- `issue` - Issue number
- `pages` - Page range (e.g., "81-97")
- `date` - Publication date/year
- `series` - Series name
- `seriesTitle` - Series title
- `seriesText` - Series text
- `journalAbbreviation` - Abbreviated journal name
- `language` - Language code
- `DOI` - Digital Object Identifier
- `ISSN` - ISSN number
- `shortTitle` - Short title
- `url` - URL
- `accessDate` - Access date
- `archive` - Archive name
- `archiveLocation` - Archive location
- `libraryCatalog` - Library catalog
- `callNumber` - Call number
- `rights` - Rights
- `extra` - Extra information
- `tags` - List of tags
- `collections` - Collection keys
- `relations` - Related items

## Book

```python
template = zot.item_template("book")
```

Additional fields:
- `publisher` - Publisher name
- `place` - Publication place
- `edition` - Edition
- `numPages` - Number of pages
- `ISBN` - ISBN number

## Conference Paper

```python
template = zot.item_template("conferencePaper")
```

Additional fields:
- `conferenceName` - Conference name
- `proceedingsTitle` - Proceedings title

## Preprint

```python
template = zot.item_template("preprint")
```

Additional fields:
- `repository` - Repository name (e.g., "arXiv")
- `archiveID` - Archive ID (e.g., "2502.12110")

## Thesis

```python
template = zot.item_template("thesis")
```

Additional fields:
- `thesisType` - Type (PhD, Master, etc.)
- `university` - University name

## Note (Child or Standalone)

```python
template = zot.item_template("note")
```

Fields:
- `note` - HTML content
- `parentItem` - Parent item key (for child notes)
- `tags` - Tags

Note content supports HTML:
```html
<p>Paragraph text</p>
<strong>Bold</strong>
<em>Italic</em>
<ul><li>List item</li></ul>
<h1>Heading</h1>
<blockquote>Quote</blockquote>
```

## Tag Format

```python
template["tags"] = [
    {"tag": "Task-050"},
    {"tag": "Memory"},
    {"tag": "Cognitive-Architecture"},
]
```

## Creator Format

```python
template["creators"] = [
    {
        "creatorType": "author",
        "firstName": "George A.",
        "lastName": "Miller"
    },
    {
        "creatorType": "author",
        "name": "Organization Name"  # For institutional authors
    }
]
```
