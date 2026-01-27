import fitz  # pip install pymupdf
import json
import os

DEFAULT_PDF_PATH = "C:/Users/dovyd/Personal_Projects/BSP-Generator/app/modules/pdfs/RM46_TRM.pdf"
DEFAULT_OUTPUT_JSON = "C:/Users/dovyd/Personal_Projects/BSP-Generator/app/modules/pdfs/out/pdf_split.json"

def generate_pdf_map(pdf_path, output_json):
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()  # Returns [level, title, page_num]
    
    # 1. Filter for only Top-Level Chapters (Level 1)
    # We clean the title immediately to make the JSON readable
    chapters = []
    for level, title, page in toc:
        if level == 1:
            # Clean title: "10 Oscillator..." -> "Oscillator..."
            # This logic splits by the first space to remove the number prefix if present
            # clean_title = title.split(' ', 1)[-1] if ' ' in title else title
            chapters.append({"title": title, "start": page})

    # 2. Sort by page number (Critical for logic to work)
    chapters.sort(key=lambda x: x["start"])

    # 3. Calculate End Pages
    final_map = {}
    total_pages = doc.page_count

    for i in range(len(chapters)):
        current_chapter = chapters[i]
        title = current_chapter["title"]
        start = current_chapter["start"]

        # If there is a next chapter, this one ends right before it
        if i + 1 < len(chapters):
            next_start = chapters[i+1]["start"]
            end = next_start - 1
        else:
            # If it's the last chapter, it goes to the end of the file
            end = total_pages

        # Safety check: Ignore weird negative ranges
        if end >= start:
            final_map[title] = {
                "start": start,
                "end": end,
                "count": end - start + 1
            }

    # 4. Save
    with open(output_json, "w") as f:
        json.dump(final_map, f, indent=2)
    
    print(f"Success! Mapped {len(final_map)} chapters. Check {output_json}.")

def split_pdf_by_map(source_pdf, map_json, output_dir="C:/Users/dovyd/Personal_Projects/BSP-Generator/app/modules/pdfs/out"):
    # 1. Setup
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    with open(map_json, "r") as f:
        sections = json.load(f)
    
    doc = fitz.open(source_pdf)
    
    print(f"Splitting {source_pdf} into {len(sections)} files...")

    # 2. Iterate and Save
    for name, data in sections.items():
        # Clean filename (remove slashes, colons that break file systems)
        safe_name = "".join([c for c in name if c.isalnum() or c in " _-\u2002"]).strip()
        filename = f"{output_dir}/{safe_name}.pdf"
        
        # Create a new empty PDF
        new_doc = fitz.open()
        
        # Insert specific pages (PyMuPDF uses 0-based indexing)
        # Your JSON map is likely 1-based from the ToC, so we subtract 1.
        start = data["start"] - 1 
        end = data["end"] - 1   
        
        # insert_pdf includes the 'to' page, so we use 'end' directly
        new_doc.insert_pdf(doc, from_page=start, to_page=end)
        
        new_doc.save(filename)
        new_doc.close()
        print(f"Saved: {filename}")

    doc.close()
    print("Done!")

if __name__ == "__main__":
    generate_pdf_map(DEFAULT_PDF_PATH, DEFAULT_OUTPUT_JSON)
    split_pdf_by_map(DEFAULT_PDF_PATH, DEFAULT_OUTPUT_JSON)