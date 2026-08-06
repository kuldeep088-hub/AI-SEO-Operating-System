"use client";

/**
 * Save-as-PDF, via the browser's own print dialogue.
 *
 * Deliberately not a headless-Chrome render pipeline. Driving Chrome over CDP
 * to produce a binary PDF means a browser binary on the server, ~300MB of it,
 * for output the client's own browser already produces from the same HTML.
 * `@media print` in globals.css strips the app chrome so the sheet prints
 * clean. If a stored PDF file is ever genuinely needed —
 * `reports.pdf_path` exists for it — scripts/build_pdf.py already has the CDP
 * plumbing to borrow.
 */
export function PrintButton() {
  return (
    <button
      type="button"
      onClick={() => window.print()}
      className="caption h-8 rounded-md border border-line px-3 text-body transition-colors hover:border-line-strong hover:text-title"
    >
      Save as PDF
    </button>
  );
}
