#!/usr/bin/env python3
"""
generate_blog.py – renders articles from articles-data.json
Uses excerpt as fallback for body_html.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

ARTICLES_JSON = "articles-data.json"
TEMPLATE_FILE = "article-template.html"
OUTPUT_DIR = "blog"

# Simple placeholder mapping
SIMPLE_MAP = {
    "title": "ARTICLE_TITLE",
    "slug": "CANONICAL_SLUG",
    "excerpt": "ARTICLE_DEK",
    "h1": "ARTICLE_H1",          # fallback to title
    "modified_date_display": "MODIFIED_DATE_DISPLAY",
    "read_time": "READ_TIME",
    "faq_intro": "FAQ_INTRO_LINE",
    "publish_date_iso": "PUBLISH_DATE_ISO",
    "modified_date_iso": "MODIFIED_DATE_ISO",
}

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
    pattern = r"<!--\s*BUILD:(\w+)\s*-->.*?<!--\s*/BUILD:\1\s*-->"
    replacements = []
    for match in re.finditer(pattern, template, re.DOTALL):
        name = match.group(1)
        if name in blocks_map:
            replacements.append((match.start(), match.end(), blocks_map[name]))
    for start, end, new_content in reversed(replacements):
        template = template[:start] + new_content + template[end:]
    return template

def generate_article_html(article, template):
    # Build context
    context = {}
    for json_key, placeholder in SIMPLE_MAP.items():
        value = article.get(json_key, "")
        if placeholder == "META_DESCRIPTION" and not value:
            value = article.get("excerpt", article.get("title", ""))
        if placeholder == "ARTICLE_H1" and not value:
            value = article.get("title", "")
        context[placeholder] = value

    # Default dates if missing
    if not context.get("PUBLISH_DATE_ISO"):
        context["PUBLISH_DATE_ISO"] = datetime.now().isoformat()
    if not context.get("MODIFIED_DATE_ISO"):
        context["MODIFIED_DATE_ISO"] = datetime.now().isoformat()
    if not context.get("MODIFIED_DATE_DISPLAY"):
        context["MODIFIED_DATE_DISPLAY"] = datetime.now().strftime("%B %d, %Y")
    if not context.get("READ_TIME"):
        context["READ_TIME"] = "3"   # fallback

    # Simple placeholder replacement
    for placeholder, value in context.items():
        template = template.replace("{{" + placeholder + "}}", str(value))

    # ----- BUILD blocks -----
    blocks = find_build_blocks(template)
    new_blocks = {}

    # JSONLD_ARTICLE
    if "JSONLD_ARTICLE" in blocks:
        schema = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": context.get("ARTICLE_TITLE", ""),
            "description": context.get("META_DESCRIPTION", ""),
            "image": "https://www.getinvoicepdf.com/og-image.png",
            "datePublished": context.get("PUBLISH_DATE_ISO", ""),
            "dateModified": context.get("MODIFIED_DATE_ISO", ""),
            "author": {"@type": "Organization", "name": "GetInvoicePDF.com", "url": "https://www.getinvoicepdf.com"},
            "publisher": {
                "@type": "Organization",
                "name": "GetInvoicePDF.com",
                "logo": {"@type": "ImageObject", "url": "https://www.getinvoicepdf.com/logo.png"}
            },
            "mainEntityOfPage": {"@type": "WebPage", "@id": f"https://www.getinvoicepdf.com/blog/{context.get('CANONICAL_SLUG', '')}/"}
        }
        new_blocks["JSONLD_ARTICLE"] = f'<script type="application/ld+json">\n{json.dumps(schema, indent=2)}\n</script>'

    # JSONLD_BREADCRUMB
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
        new_blocks["JSONLD_BREADCRUMB"] = f'<script type="application/ld+json">\n{json.dumps(breadcrumb, indent=2)}\n</script>'

    # JSONLD_FAQ
    if "JSONLD_FAQ" in blocks:
        faq_list = article.get("faq", [])
        if faq_list:
            main_entity = [{"@type": "Question", "name": item.get("question", ""), "acceptedAnswer": {"@type": "Answer", "text": item.get("answer", "")}} for item in faq_list]
            faq_schema = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": main_entity}
            new_blocks["JSONLD_FAQ"] = f'<script type="application/ld+json">\n{json.dumps(faq_schema, indent=2)}\n</script>'
        else:
            new_blocks["JSONLD_FAQ"] = ""

    # ARTICLE_BODY – fallback to excerpt if body_html missing
    if "ARTICLE_BODY" in blocks:
        body_html = article.get("body_html", "")
        if not body_html:
            # Generate a simple body from excerpt and maybe a standard intro
            excerpt = article.get("excerpt", "")
            title = article.get("title", "")
            # Wrap excerpt in paragraphs, add a simple H2 based on title
            body_html = f"<h2 class='text-2xl font-bold text-slate-900 mt-2 mb-3 border-l-4 border-brand-500 pl-4'>Understanding This Invoice Structure</h2>"
            body_html += f"<p class='text-slate-600 leading-relaxed mb-4'>{excerpt}</p>"
            # You can add more default paragraphs if needed
        new_blocks["ARTICLE_BODY"] = body_html

    # FAQ_SECTION
    if "FAQ_SECTION" in blocks:
        faq_list = article.get("faq", [])
        if faq_list and "FAQ_ITEM" in blocks:
            faq_item_inner = blocks["FAQ_ITEM"][2]
            rendered_items = []
            for item in faq_list:
                q = item.get("question", "")
                a = item.get("answer", "")
                rendered = faq_item_inner.replace("{{FAQ_QUESTION}}", q).replace("{{FAQ_ANSWER}}", a)
                rendered_items.append(rendered)
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
            new_blocks["FAQ_SECTION"] = ""

    # RELATED_CARD
    if "RELATED_CARD" in blocks:
        related_list = article.get("related", [])
        if related_list:
            card_template_inner = blocks["RELATED_CARD"][2]
            rendered_cards = []
            for rel in related_list:
                slug = rel.get("slug", "")
                title = rel.get("title", "")
                card = card_template_inner.replace("{{RELATED_SLUG}}", slug).replace("{{RELATED_TITLE}}", title)
                rendered_cards.append(card)
            new_blocks["RELATED_CARD"] = "\n".join(rendered_cards)
        else:
            new_blocks["RELATED_CARD"] = ""

    # Apply all block replacements
    template = replace_build_blocks(template, new_blocks)

    # Remove any leftover {{...}} tokens
    template = re.sub(r"\{\{[^}]+\}\}", "", template)

    return template

def main():
    data = load_json(ARTICLES_JSON)
    template = read_template(TEMPLATE_FILE)
    articles = data.get("articles", [])
    if not articles:
        print("No articles found.")
        return

    for article in articles:
        slug = article.get("slug", "")
        if not slug:
            continue
        print(f"Generating: {slug}")
        html = generate_article_html(article, template)
        out_path = os.path.join(OUTPUT_DIR, f"{slug}.html")
        write_output(out_path, html)

    print(f"✅ Generated {len(articles)} articles in '{OUTPUT_DIR}/'")

if __name__ == "__main__":
    main()
