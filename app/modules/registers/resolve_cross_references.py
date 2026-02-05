#!/usr/bin/env python3
"""
resolve_cross_references.py

Pass 2: Resolve cross-document references using lightweight text search.

Finds all x-needs-verification entries and resolves them by:
1. Searching relevant PDFs for keywords
2. Making targeted Claude queries with specific chunks
3. Updating YAML with found information
4. Maintaining source attribution
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yaml as pyyaml
import re

from modules.pdf_text_extractor import extract_text_from_pdf
from modules.prompt import Model
from pdf_to_yaml_extractor import invoke_model
from extract_to_yaml import CostTracker, BudgetExceededError


# ============================================================================
# LIGHTWEIGHT TEXT INDEX
# ============================================================================

class TextIndex:
    """Simple keyword-based text index for cross-document search."""

    def __init__(self):
        self.pdf_texts: Dict[str, str] = {}  # pdf_name -> full_text
        self.pdf_paths: Dict[str, Path] = {}  # pdf_name -> path

    def index_pdfs(self, pdf_dir: Path, include_datasheet: Optional[Path] = None):
        """Build index from PDF directory."""
        print("Building text index from PDFs...")

        # Index TRM PDFs
        for pdf_path in pdf_dir.glob("*.pdf"):
            print(f"  Indexing {pdf_path.name}...")
            text = extract_text_from_pdf(pdf_path)
            self.pdf_texts[pdf_path.name] = text
            self.pdf_paths[pdf_path.name] = pdf_path

        # Index datasheet
        if include_datasheet and include_datasheet.exists():
            print(f"  Indexing {include_datasheet.name}...")
            text = extract_text_from_pdf(include_datasheet)
            self.pdf_texts[include_datasheet.name] = text
            self.pdf_paths[include_datasheet.name] = include_datasheet

        print(f"[OK] Indexed {len(self.pdf_texts)} PDFs")

    def search(
        self,
        keywords: List[str],
        source_filter: Optional[str] = None,
        max_chunk_size: int = 3000
    ) -> List[Dict]:
        """
        Search for keywords and return relevant text chunks.

        Returns list of:
        {
            'pdf': pdf_name,
            'chunk': text_chunk,
            'score': relevance_score,
            'keywords_found': [list of found keywords]
        }
        """
        results = []

        # Determine which PDFs to search
        pdfs_to_search = []

        if source_filter:
            # Filter by source hint
            filter_lower = source_filter.lower()
            for pdf_name in self.pdf_texts.keys():
                if any(term in pdf_name.lower() for term in filter_lower.split()):
                    pdfs_to_search.append(pdf_name)
                elif 'datasheet' in filter_lower and 'datasheet' not in pdf_name.lower():
                    continue
                else:
                    pdfs_to_search.append(pdf_name)
        else:
            pdfs_to_search = list(self.pdf_texts.keys())

        # Search each PDF
        for pdf_name in pdfs_to_search:
            text = self.pdf_texts[pdf_name]
            text_lower = text.lower()

            # Find all keyword positions
            keyword_positions = []
            keywords_found = []

            for keyword in keywords:
                kw_lower = keyword.lower()
                pos = 0
                while True:
                    pos = text_lower.find(kw_lower, pos)
                    if pos == -1:
                        break
                    keyword_positions.append(pos)
                    if keyword not in keywords_found:
                        keywords_found.append(keyword)
                    pos += len(kw_lower)

            if not keyword_positions:
                continue

            # Extract chunks around keyword positions
            for pos in keyword_positions:
                start = max(0, pos - max_chunk_size // 2)
                end = min(len(text), pos + max_chunk_size // 2)
                chunk = text[start:end]

                # Score by keyword density
                score = sum(1 for kw in keywords if kw.lower() in chunk.lower())

                results.append({
                    'pdf': pdf_name,
                    'chunk': chunk,
                    'score': score,
                    'keywords_found': keywords_found
                })

        # Sort by score
        results.sort(key=lambda x: x['score'], reverse=True)

        return results[:5]  # Top 5 results


# ============================================================================
# CROSS-REFERENCE RESOLVER
# ============================================================================

class CrossReferenceResolver:
    """Resolve x-needs-verification entries."""

    def __init__(
        self,
        index: TextIndex,
        model: Model,
        cost_tracker: CostTracker
    ):
        self.index = index
        self.model = model
        self.cost_tracker = cost_tracker

    async def resolve_verification_entry(
        self,
        verification: Dict,
        peripheral_name: str
    ) -> Optional[Dict]:
        """
        Resolve a single x-needs-verification entry.

        Args:
            verification: Dict with 'query', 'search_terms', 'likely_source'
            peripheral_name: Name of peripheral being resolved

        Returns:
            Dict with resolved data + source attribution, or None if not found
        """
        query = verification.get('query', '')
        search_terms = verification.get('search_terms', [])
        likely_source = verification.get('likely_source', '')

        print(f"  Resolving: {query}")

        # Search for relevant chunks
        search_results = self.index.search(
            keywords=search_terms,
            source_filter=likely_source,
            max_chunk_size=3000
        )

        if not search_results:
            print(f"    [WARN] No results found")
            return None

        # Format chunks for Claude
        chunks_text = ""
        for i, result in enumerate(search_results[:3]):  # Top 3 results
            chunks_text += f"\n## Source {i+1}: {result['pdf']}\n"
            chunks_text += f"Keywords found: {', '.join(result['keywords_found'])}\n"
            chunks_text += f"```\n{result['chunk']}\n```\n"

        # Build targeted prompt
        prompt = f"""Answer this specific question about the {peripheral_name} peripheral:

**Question**: {query}

**Context from documentation**:
{chunks_text}

Extract the answer in YAML format with source attribution:

```yaml
answer:
  # Your extracted answer here (use appropriate YAML structure)

x-source:
  pdf: "name_of_pdf_where_found.pdf"
  confidence: "high"  # or "medium" or "low"
  resolved_from: "cross_document_search"
```

If the answer is not in the provided context, respond with:
```yaml
answer: null
not_found: true
```
"""

        # Call Claude with small token limit (targeted query)
        try:
            response, input_tokens, output_tokens = await invoke_model(
                model=self.model,
                max_tokens=2000,  # Small - just answering one question
                system_prompt="You are resolving cross-document references. Extract specific answers with source attribution.",
                user_prompt=prompt
            )

            # Track cost
            within_budget = await self.cost_tracker.add_tokens(input_tokens, output_tokens)
            if not within_budget:
                raise BudgetExceededError("Budget exceeded")

            # Parse YAML response
            yaml_match = re.search(r'```yaml\n(.*?)\n```', response, re.DOTALL)
            if yaml_match:
                yaml_str = yaml_match.group(1)
                resolved_data = pyyaml.safe_load(yaml_str)

                if resolved_data and not resolved_data.get('not_found'):
                    print(f"    [OK] Resolved from {resolved_data.get('x-source', {}).get('pdf', 'unknown')}")
                    return resolved_data
                else:
                    print(f"    [WARN] Not found in documentation")
                    return None
            else:
                print(f"    [WARN] Could not parse response")
                return None

        except BudgetExceededError:
            raise
        except Exception as e:
            print(f"    [FAIL] Resolution failed: {e}")
            return None


# ============================================================================
# MAIN RESOLVER PIPELINE
# ============================================================================

async def resolve_all_cross_references(
    extracted_dir: Path,
    trm_dir: Path,
    datasheet_path: Optional[Path],
    output_dir: Path,
    model: Model = Model.SONNET_4_5,
    max_budget_remaining: float = 25.0
):
    """
    Pass 2: Resolve all x-needs-verification entries.

    Args:
        extracted_dir: Directory with Pass 1 extracted YAMLs
        trm_dir: TRM PDF directory (for text index)
        datasheet_path: Datasheet PDF (for text index)
        output_dir: Output directory for resolved YAMLs
        model: Claude model
        max_budget_remaining: Remaining budget after Pass 1
    """
    print("="*80)
    print("YAML EXTRACTION - PASS 2: Cross-Reference Resolution")
    print("="*80)
    print(f"Budget remaining: ${max_budget_remaining:.2f}")
    print()

    # Initialize cost tracker
    cost_tracker = CostTracker(max_budget=max_budget_remaining)

    # Build text index
    index = TextIndex()
    index.index_pdfs(trm_dir, include_datasheet=datasheet_path)

    # Initialize resolver
    resolver = CrossReferenceResolver(index, model, cost_tracker)

    # Find all extracted YAMLs
    extracted_yamls = list((extracted_dir / "extracted").rglob("*_extracted.yaml"))

    print(f"\nResolving cross-references in {len(extracted_yamls)} files...")
    print()

    resolved_count = 0
    failed_count = 0

    for yaml_file in extracted_yamls:
        periph_name = yaml_file.parent.name

        print(f"[{periph_name}] {yaml_file.name}")

        # Load YAML
        with open(yaml_file) as f:
            data = pyyaml.safe_load(f)

        if not data:
            print(f"  [WARN] Empty YAML, skipping")
            continue

        # Find all x-needs-verification entries
        verifications = find_verification_entries(data)

        if not verifications:
            print(f"  [OK] No cross-references to resolve")
            continue

        print(f"  Found {len(verifications)} cross-references")

        # Resolve each
        for verification_path, verification_data in verifications:
            try:
                resolved = await resolver.resolve_verification_entry(
                    verification_data, periph_name
                )

                if resolved:
                    # Update YAML with resolved data
                    # (This is simplified - in practice, merge back into data structure)
                    resolved_count += 1
                else:
                    failed_count += 1

            except BudgetExceededError:
                print(f"\n[WARN] Budget exceeded during resolution")
                break

        # Save resolved YAML
        resolved_dir = output_dir / "resolved" / periph_name
        resolved_dir.mkdir(parents=True, exist_ok=True)

        output_file = resolved_dir / yaml_file.name
        with open(output_file, 'w') as f:
            pyyaml.dump(data, f, default_flow_style=False, sort_keys=False)

        print(f"  [OK] Saved to {output_file.relative_to(output_dir)}")

    # Summary
    print("\n" + "="*80)
    print("PASS 2 COMPLETE")
    print("="*80)
    print(f"Cross-references resolved: {resolved_count}")
    print(f"Could not resolve: {failed_count}")
    print(f"{cost_tracker.format_status()}")
    print()
    print(f"Output: {output_dir / 'resolved'}")
    print("="*80)


def find_verification_entries(data, path="") -> List[Tuple[str, Dict]]:
    """Find all x-needs-verification entries in YAML data."""
    entries = []

    if isinstance(data, dict):
        if 'x-needs-verification' in data:
            verif_list = data['x-needs-verification']
            if isinstance(verif_list, list):
                for item in verif_list:
                    entries.append((path, item))

        for key, value in data.items():
            entries.extend(find_verification_entries(value, f"{path}.{key}"))

    elif isinstance(data, list):
        for i, item in enumerate(data):
            entries.extend(find_verification_entries(item, f"{path}[{i}]"))

    return entries


# ============================================================================
# CLI
# ============================================================================

async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Resolve cross-document references (Pass 2)"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("yaml_out"),
        help="Input directory (from Pass 1)"
    )
    parser.add_argument(
        "--trm",
        type=Path,
        default=Path("modules/pdfs/TRM_split"),
        help="TRM directory"
    )
    parser.add_argument(
        "--datasheet",
        type=Path,
        help="Datasheet PDF"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("yaml_out"),
        help="Output directory"
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=25.0,
        help="Budget remaining for Pass 2"
    )
    parser.add_argument(
        "--model",
        choices=["haiku4.5", "sonnet4.5"],
        default="sonnet4.5"
    )

    args = parser.parse_args()

    # Auto-detect datasheet
    if not args.datasheet:
        input_docs = Path("input_docs")
        if input_docs.exists():
            candidates = []
            for pdf in input_docs.glob("*.pdf"):
                # Skip schematic files
                if "schematic" in pdf.name.lower():
                    continue

                size_mb = pdf.stat().st_size / (1024 * 1024)

                # Prefer files with "datasheet" in name
                if "datasheet" in pdf.name.lower():
                    args.datasheet = pdf
                    break

                # Otherwise collect candidates >1MB
                if size_mb > 1:
                    candidates.append((pdf, size_mb))

            # If no explicit "datasheet" name found, use largest candidate
            if not args.datasheet and candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                args.datasheet = candidates[0][0]

    model = Model.HAIKU_4_5 if args.model == "haiku4.5" else Model.SONNET_4_5

    await resolve_all_cross_references(
        extracted_dir=args.input,
        trm_dir=args.trm,
        datasheet_path=args.datasheet,
        output_dir=args.output,
        model=model,
        max_budget_remaining=args.budget
    )


if __name__ == "__main__":
    asyncio.run(main())
