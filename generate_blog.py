#!/usr/bin/env python3
"""
generate_blog.py
Reads articles-data.json, renders each article through article-template.html,
and writes the final HTML to blog/<slug>.html.
Handles {{PLACEHOLDER}} and <!-- BUILD:... --> blocks.
Missing keys are replaced with empty strings.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

# -------------------------------------------------------------
# Configuration
# -------------------------------------------------------------
ARTICLES_JSON = "articles-data.json"
TEMPLATE_FILE = "article-template.html"
OUTPUT_DIR = "blog"

# Simple placeholder mapping from JSON keys to template placeholders.
# (Add more as your JSON structure evolves)
SIMPLE_MAP = {
    "title": "ARTICLE_TITLE",
    "slug": "CANONICAL_SLUG",
    "excerpt": "ARTICLE_DEK",
    # If your JSON has a separate meta_description, add it.
    # Otherwise we reuse title for meta description.
    "meta_description": "META_DESCRIPTION",
    "h1": "ARTICLE_H1",           # If not present, falls back to title
    "modified_date_display": "MODIFIED_DATE_DISPLAY",
    "read_time": "READ_TIME",
    "faq_intro": "FAQ_INTRO_LINE",
    "publish_date_iso": "PUBLISH_DATE_ISO",
    "modified_date_iso": "MODIFIED_DATE_ISO",
    # These are used inside BUILD blocks – we'll set them separately
}

# -------------------------------------------------------------
# Utilities
# -------------------------------------------------------------
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def read_template(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_output(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def find_build_blocks(template):
    """
    Returns a dict: marker_name -> (start_index, end_index, inner_content)
    where inner_content is the text between <!-- BUILD:NAME --> and <!-- /BUILD:NAME -->.
    """
    pattern = r"<!--\s*BUILD:(\w+)\s*-->(.*?)<!--\s*/BUILD:\1\s*-->"
    blocks = {}
    for match in re.finditer(pattern, template, re.DOTALL):
        name = match.group(1)
        start = match.start()
        end = match.end()
        inner = match.group(2)
        blocks[name] = (start, end, inner)
    return blocks

def replace_build_blocks(template, blocks_map):
    """
    blocks_map: dict name -> new_content (string)
    Replaces each BUILD block with its new content.
    """
    # We'll replace from the end to avoid shifting indices.
    # First, collect all blocks with their positions.
    pattern = r"<!--\s*BUILD:(\w+)\s*-->.*?<!--\s*/BUILD:\1\s*-->"
    replacements = []
    for match in re.finditer(pattern, template, re.DOTALL):
        name = match.group(1)
        if name in blocks_map:
            replacements.append((match.start(), match.end(), blocks_map[name]))
    # Apply replacements in reverse order
    for start, end, new_content in reversed(replacements):
        template = template[:start] + new_content + template[end:]
    return template

def generate_article_html(article, template):
    """
    Renders a single article.
    """
    # 1. Build simple context from article data.
    context = {}
    for json_key, placeholder in SIMPLE_MAP.items():
        value = article.get(json_key, "")
        # For META_DESCRIPTION, if missing, use excerpt or title.
        if placeholder == "META_DESCRIPTION" and not value:
            value = article.get("excerpt", article.get("title", ""))
        # For ARTICLE_H1, if missing, use title.
        if placeholder == "ARTICLE_H1" and not value:
            value = article.get("title", "")
        # For date ISO, we might need to format – assume they are strings in JSON.
        context[placeholder] = value

    # If the JSON doesn't provide separate ISO dates, we can fall back to current date.
    if "PUBLISH_DATE_ISO" not in context or not context["PUBLISH_DATE_ISO"]:
        context["PUBLISH_DATE_ISO"] = datetime.now().isoformat()
    if "MODIFIED_DATE_ISO" not in context or not context["MODIFIED_DATE_ISO"]:
        context["MODIFIED_DATE_ISO"] = datetime.now().isoformat()

    # 2. Replace all {{PLACEHOLDER}} in the template.
    for placeholder, value in context.items():
        template = template.replace("{{" + placeholder + "}}", str(value))

    # 3. Handle BUILD blocks.
    blocks = find_build_blocks(template)
    new_blocks = {}

    # ---- JSONLD_ARTICLE ----
    if "JSONLD_ARTICLE" in blocks:
        schema = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": context.get("ARTICLE_TITLE", ""),
            "description": context.get("META_DESCRIPTION", ""),
            "image": "https://www.getinvoicepdf.com/og-image.png",
            "datePublished": context.get("PUBLISH_DATE_ISO", ""),
            "dateModified": context.get("MODIFIED_DATE_ISO", ""),
            "author": {
                "@type": "Organization",
                "name": "GetInvoicePDF.com",
                "url": "https://www.getinvoicepdf.com"
            },
            "publisher": {
                "@type": "Organization",
                "name": "GetInvoicePDF.com",
                "logo": {
                    "@type": "ImageObject",
                    "url": "https://www.getinvoicepdf.com/logo.png"
                }
            },
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": f"https://www.getinvoicepdf.com/blog/{context.get('CANONICAL_SLUG', '')}/"
            }
        }
        jsonld = f'<script type="application/ld+json">\n{json.dumps(schema, indent=2)}\n</script>'
        new_blocks["JSONLD_ARTICLE"] = jsonld

    # ---- JSONLD_BREADCRUMB ----
    if "JSONLD_BREADCRUMB" in blocks:
        breadcrumb = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://www.getinvoicepdf.com/"},
                {"@type": "ListItem", "position": 2, "name": "Invoicing Guides", "item": "https://www.getinvoicepdf.com/blog/"},
                {"@type": "ListItem", "position": 3, "name": context.get("ARTICLE_TITLE", ""), "item": f"https://www.getinvoicepdf.com/blog/{context.get('CANONICAL_SLUG', '')}/"}
            ]
        }
        jsonld = f'<script type="application/ld+json">\n{json.dumps(breadcrumb, indent=2)}\n</script>'
        new_blocks["JSONLD_BREADCRUMB"] = jsonld

    # ---- JSONLD_FAQ ----
    if "JSONLD_FAQ" in blocks:
        faq_list = article.get("faq", [])
        if faq_list:
            main_entity = []
            for item in faq_list:
                main_entity.append({
                    "@type": "Question",
                    "name": item.get("question", ""),
                    "acceptedAnswer": {"@type": "Answer", "text": item.get("answer", "")}
                })
            faq_schema = {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": main_entity
            }
            jsonld = f'<script type="application/ld+json">\n{json.dumps(faq_schema, indent=2)}\n</script>'
        else:
            jsonld = ""  # Remove the block if no FAQ data
        new_blocks["JSONLD_FAQ"] = jsonld

    # ---- ARTICLE_BODY ----
    if "ARTICLE_BODY" in blocks:
        # Use pre-rendered body_html if present, otherwise fallback to a simple placeholder.
        body_html = article.get("body_html", "")
        # If the template's ARTICLE_BODY contains a placeholder structure, we could also
        # generate body from paragraphs, but we assume body_html is provided.
        new_blocks["ARTICLE_BODY"] = body_html

    # ---- FAQ_SECTION ----
    if "FAQ_SECTION" in blocks:
        # Get the inner FAQ_ITEM template (if present) to repeat.
        faq_block_outer = blocks.get("FAQ_SECTION")
        faq_items_template = None
        if "FAQ_ITEM" in blocks:
            faq_items_template = blocks["FAQ_ITEM"][2]  # inner content of FAQ_ITEM block

        faq_list = article.get("faq", [])
        if faq_list and faq_items_template:
            rendered_items = []
            for item in faq_list:
                q = item.get("question", "")
                a = item.get("answer", "")
                rendered = faq_items_template.replace("{{FAQ_QUESTION}}", q).replace("{{FAQ_ANSWER}}", a)
                rendered_items.append(rendered)
            faq_html = "\n".join(rendered_items)
            # The FAQ_SECTION block contains the wrapper structure; we need to replace the inner part.
            # But we can simply replace the entire block with our generated FAQ section.
            # However, we must keep the outer section tags. Easier: we replace the FAQ_SECTION block
            # with a full rendered section. We'll use the template's FAQ_SECTION inner as a base.
            # But to preserve the surrounding divs, we'll create a new section.
            # Simpler: we can generate the whole FAQ section from scratch using the FAQ_ITEM template.
            # Let's rebuild the FAQ_SECTION content:
            intro = context.get("FAQ_INTRO_LINE", "")
            faq_section_html = f'''
<section class="faq-section max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pb-16">
    <h2 class="text-2xl font-bold text-slate-900 mb-2">Frequently Asked Questions</h2>
    <p class="text-slate-500 mb-4">{intro}</p>
    <div class="faq-list divide-y divide-slate-200 border-t border-slate-200">
        {''.join(rendered_items)}
    </div>
</section>
'''
            new_blocks["FAQ_SECTION"] = faq_section_html
        else:
            # If no FAQ items, remove the entire FAQ section.
            new_blocks["FAQ_SECTION"] = ""

    # ---- RELATED_CARD ----
    if "RELATED_CARD" in blocks:
        related_list = article.get("related", [])
        if related_list:
            # related_list is expected to be a list of dicts with slug and title.
            card_template = blocks["RELATED_CARD"][2]  # inner content of RELATED_CARD block
            rendered_cards = []
            for rel in related_list:
                slug = rel.get("slug", "")
                title = rel.get("title", "")
                card = card_template.replace("{{RELATED_SLUG}}", slug).replace("{{RELATED_TITLE}}", title)
                rendered_cards.append(card)
            related_html = "\n".join(rendered_cards)
            # Wrap in the outer section structure if needed; but the template has the section wrapper.
            # The BUILD:RELATED_CARD is inside the <div class="grid ...">, so we replace just the cards.
            new_blocks["RELATED_CARD"] = related_html
        else:
            # If no related articles, we may want to remove the entire section.
            # We'll just replace the block with empty, but the surrounding section will remain.
            # To remove the whole section, we'd need to handle that, but we'll leave it.
            new_blocks["RELATED_CARD"] = ""

    # Apply all block replacements
    template = replace_build_blocks(template, new_blocks)

    # Clean up any leftover placeholder tokens that weren't replaced.
    # Replace any remaining {{...}} with empty string to avoid broken output.
    template = re.sub(r"\{\{[^}]+\}\}", "", template)

    return template

# -------------------------------------------------------------
# Main execution
# -------------------------------------------------------------
def main():
    data = load_json(ARTICLES_JSON)
    template = read_template(TEMPLATE_FILE)

    articles = data.get("articles", [])
    if not articles:
        print("No articles found in JSON.")
        return

    for article in articles:
        slug = article.get("slug", "")
        if not slug:
            print("Skipping article without slug:", article.get("title", "unknown"))
            continue

        print(f"Generating: {slug}")
        html = generate_article_html(article, template)
        out_path = os.path.join(OUTPUT_DIR, f"{slug}.html")
        write_output(out_path, html)

    print(f"✅ Generated {len(articles)} articles in '{OUTPUT_DIR}/'")

if __name__ == "__main__":
    main()
