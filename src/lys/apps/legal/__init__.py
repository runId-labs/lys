"""
Legal application for versioned legal documents with provable, version-bound consent.

This app provides:
- Versioned, immutable legal documents (terms of use, sales terms, privacy policy)
  rendered to PDF via `lys.core.utils.pdf` and stored through the shared storage backend.
- Append-only consent proofs carrying a self-contained identity snapshot that survives
  later anonymization of the user account.
- Retention and anonymization reconciliation tasks (GDPR art. 17).

The document text (Markdown source) is application-owned and declared in `settings.legal`;
lys owns the machinery (rendering, storage, versioning, consent proof).
"""
